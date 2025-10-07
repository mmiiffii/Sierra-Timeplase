import cv2
import os
import numpy as np
from glob import glob
from datetime import datetime

# === Config ===
FOLDERS = ["images_10min", "images_inbetween"]
OUTPUT_DIR = "timelapses"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Clean old video files
for old_file in glob(os.path.join(OUTPUT_DIR, "*.mp4")):
    os.remove(old_file)

OUTPUT_VIDEO = os.path.join(
    OUTPUT_DIR, f"timelapse_combined_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
)
FPS = 24

# === Helper functions ===

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


def enhance_frame(frame):
    """Apply denoise and contrast enhancement"""
    denoised = cv2.fastNlMeansDenoisingColored(frame, None, 5, 5, 7, 21)
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.equalizeHist(l)
    enhanced = cv2.merge((l, a, b))
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


def is_glitched(frame):
    """Detect glitched, blank, or partially loaded frames"""
    if frame is None:
        return True
    if frame.shape[0] < 100 or frame.shape[1] < 100:
        # likely incomplete download
        return True
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_intensity = np.mean(gray)
    std_intensity = np.std(gray)
    if mean_intensity < 10 or mean_intensity > 245:
        # too dark or too bright
        return True
    if std_intensity < 5:
        # almost flat / blank
        return True
    return False


# === Collect & sort images ===
images = []
for folder in FOLDERS:
    for f in glob(os.path.join(folder, "*.jpg")):
        ts = extract_timestamp(f)
        images.append((ts, f))

images = sorted(images, key=lambda x: x[0])

if not images:
    raise ValueError("❌ No images found in either folder!")

# === Prepare video writer ===
first_frame = cv2.imread(images[0][1])
if first_frame is None:
    raise ValueError(f"❌ Could not read first image: {images[0][1]}")
height, width, _ = first_frame.shape
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (width, height))

print(f"🎬 Creating 24fps timelapse with {len(images)} frames...")

good_count, skipped_count = 0, 0

for ts, img_file in images:
    frame = cv2.imread(img_file)
    if is_glitched(frame):
        print(f"⚠️ Skipping glitched or blank frame: {img_file}")
        skipped_count += 1
        continue
    frame = cv2.resize(frame, (width, height))
    enhanced = enhance_frame(frame)
    out.write(enhanced)
    good_count += 1

out.release()

print(f"✅ Timelapse saved as {OUTPUT_VIDEO}")
print(f"✅ Used {good_count} frames, skipped {skipped_count} bad ones.")
