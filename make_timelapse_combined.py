# make_timelapse_combined.py
import cv2
import numpy as np
import os
import re
from glob import glob
from datetime import datetime

# === Configurable thresholds (tweak if needed) ===
FOLDERS = ["images_10min", "images_inbetween"]
OUTPUT_DIR = "timelapses"
FPS = 24

# detection thresholds
MIN_DIM = 100                 # min width/height to accept frame
MIN_STD = 10                  # if grayscale std < this -> nearly flat (bad)
DOMINANT_BIN_RATIO = 0.50     # if one grayscale bin > ratio -> nearly uniform (bad)
PERCENT_BLACK = 0.55          # if >55% pixels <= BLACK_LEVEL -> black screen (bad)
PERCENT_WHITE = 0.55          # if >55% pixels >= WHITE_LEVEL -> white/overexposed (bad)
BLACK_LEVEL = 15
WHITE_LEVEL = 240
HALF_DIFF_THRESH = 60         # left/right mean diff > threshold when one side near-black/white -> bad

os.makedirs(OUTPUT_DIR, exist_ok=True)

# remove any previous output to ensure single file per run
for old_file in glob(os.path.join(OUTPUT_DIR, "*.mp4")):
    try:
        os.remove(old_file)
    except Exception:
        pass

OUTPUT_VIDEO = os.path.join(
    OUTPUT_DIR, f"timelapse_combined_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
)

# --- Helpers ---
def extract_timestamp(path: str) -> datetime:
    """Find pattern YYYYMMDD_HHMMSS in filename and parse it; fallback to min datetime."""
    base = os.path.basename(path)
    m = re.search(r'(\d{8}_\d{6})', base)
    if not m:
        return datetime.min
    try:
        return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
    except Exception:
        return datetime.min

def is_bad_frame(frame):
    """Return (True, reason) if frame should be skipped."""
    if frame is None:
        return True, "unreadable"

    h, w = frame.shape[:2]
    if h < MIN_DIM or w < MIN_DIM:
        return True, f"too_small ({w}x{h})"

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = float(np.mean(gray))
    std = float(np.std(gray))

    # quick black/white screen checks
    black_ratio = float(np.sum(gray <= BLACK_LEVEL)) / (h * w)
    white_ratio = float(np.sum(gray >= WHITE_LEVEL)) / (h * w)
    if black_ratio >= PERCENT_BLACK:
        return True, f"mostly_black ({black_ratio:.2f})"
    if white_ratio >= PERCENT_WHITE:
        return True, f"mostly_white ({white_ratio:.2f})"

    # low variation (flat / mid-gray)
    if std < MIN_STD:
        return True, f"low_std ({std:.2f})"

    # dominant histogram bin (nearly uniform single intensity)
    hist = cv2.calcHist([gray], [0], None, [256], [0,256]).flatten()
    dominant_ratio = float(np.max(hist)) / (h * w)
    if dominant_ratio >= DOMINANT_BIN_RATIO:
        return True, f"dominant_bin ({dominant_ratio:.2f})"

    # left/right half check: detect half-loaded frames where one side blank
    left_mean = float(np.mean(gray[:, :w//2]))
    right_mean = float(np.mean(gray[:, w//2:]))
    if abs(left_mean - right_mean) > HALF_DIFF_THRESH:
        # check if one side is extreme (near black or near white)
        if left_mean <= (BLACK_LEVEL + 10) or right_mean <= (BLACK_LEVEL + 10):
            return True, f"half_blank (L={left_mean:.1f},R={right_mean:.1f})"
        if left_mean >= (WHITE_LEVEL - 10) or right_mean >= (WHITE_LEVEL - 10):
            return True, f"half_white (L={left_mean:.1f},R={right_mean:.1f})"

    # optional: very high-frequency noise (rare), skip if laplacian var extremely high
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if lap_var > 1e5:
        return True, f"excessive_lap_var ({lap_var:.1f})"

    return False, ""

# === Collect & sort images ===
images = []
for folder in FOLDERS:
    for f in glob(os.path.join(folder, "*.jpg")):
        images.append((extract_timestamp(f), f))

images = sorted(images, key=lambda x: x[0])

if not images:
    raise ValueError("❌ No images found in either folder!")

# find first valid frame to initialize video size
init_frame = None
for _, p in images:
    f = cv2.imread(p)
    bad, reason = is_bad_frame(f)
    if not bad:
        init_frame = f
        break

if init_frame is None:
    raise ValueError("❌ Could not find any valid frame to initialize the video. All frames appear bad.")

height, width = init_frame.shape[:2]
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (width, height))

print(f"🎬 Creating {FPS} fps timelapse from {len(images)} candidate frames...")

used = 0
skipped = 0
valid_times = []

for ts, path in images:
    frame = cv2.imread(path)
    bad, reason = is_bad_frame(frame)
    if bad:
        skipped += 1
        print(f"⚠️ Skipping {os.path.basename(path)} -> {reason}")
        continue
    # ensure consistent size
    if frame.shape[:2] != (height, width):
        frame = cv2.resize(frame, (width, height))
    out.write(frame)
    used += 1
    valid_times.append(ts)

out.release()

if valid_times:
    start_time = min(valid_times)
    end_time = max(valid_times)
    print(f"🕒 Frame range used: {start_time} → {end_time}")

print(f"✅ Timelapse saved as {OUTPUT_VIDEO}")
print(f"✅ Used {used} frames, skipped {skipped} bad frames.")
