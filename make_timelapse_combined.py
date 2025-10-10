import cv2
import numpy as np
import os
from glob import glob
from datetime import datetime

# === Configuration ===
FOLDERS = ["images_10min", "images_inbetween"]
OUTPUT_DIR = "timelapses"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Clean any previous videos
for old_file in glob(os.path.join(OUTPUT_DIR, "*.mp4")):
    os.remove(old_file)

OUTPUT_VIDEO = os.path.join(
    OUTPUT_DIR, f"timelapse_combined_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
)
FPS = 24


# --- Helper functions ---
def extract_timestamp(path: str) -> datetime:
    """Extract timestamp from filenames like image_20250922_120000.jpg"""
    base = os.path.basename(path)
    parts = base.split("_")
    if len(parts) < 3:
        return datetime.min
    try:
        return datetime.strptime(parts[1] + "_" + parts[2].split(".")[0], "%Y%m%d_%H%M%S")
    except ValueError:
        return datetime.min


def is_valid_frame(frame):
    """Detect unreadable, blank, or glitched frames"""
    if frame is None:
        return False

    h, w, _ = frame.shape
    if h < 100 or w < 100:
        return False

    # Convert to grayscale for checks
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # --- Check 1: Blank or frozen frame (very low contrast)
    std_dev = np.std(gray)
    if std_dev < 5:  # very little variation → likely blank or frozen
        return False

    # --- Check 2: Glitched image (extreme high-frequency noise)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if lap_var > 8000:  # unusually sharp → possibly corrupted
        return False

    return True


# === Gather all images chronologically ===
images = []
for folder in FOLDERS:
    for f in glob(os.path.join(folder, "*.jpg")):
        ts = extract_timestamp(f)
        images.append((ts, f))

images = sorted(images, key=lambda x: x[0])

if not images:
    raise ValueError("❌ No images found in either folder!")

# === Initialize video writer ===
frame = None
for _, path in images:
    frame = cv2.imread(path)
    if is_valid_frame(frame):
        break
if frame is None:
    raise ValueError("❌ Could not find any valid frame to initialize video.")

height, width, _ = frame.shape
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (width, height))

print(f"🎬 Creating 24 fps timelapse with {len(images)} total frames...")

used, skipped = 0, 0
valid_times = []

for ts, path in images:
    frame = cv2.imread(path)
    if not is_valid_frame(frame):
        print(f"⚠️ Skipping glitched/blank frame: {path}")
        skipped += 1
        continue

    frame = cv2.resize(frame, (width, height))
    out.write(frame)
    valid_times.append(ts)
    used += 1

out.release()

if valid_times:
    start_time = min(valid_times)
    end_time = max(valid_times)
    print(f"🕒 Frame range: {start_time} → {end_time}")

print(f"✅ Timelapse saved as {OUTPUT_VIDEO}")
print(f"✅ Used {used} frames, skipped {skipped} bad frames.")
