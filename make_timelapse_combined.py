import cv2
import os
from glob import glob
from datetime import datetime

# === Config ===
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
    """Skip unreadable or empty frames"""
    if frame is None:
        return False
    if frame.shape[0] < 100 or frame.shape[1] < 100:
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
frame = cv2.imread(images[0][1])
if not is_valid_frame(frame):
    raise ValueError(f"❌ Could not read first valid image.")
height, width, _ = frame.shape

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (width, height))

print(f"🎬 Creating 24fps timelapse with {len(images)} frames...")

used, skipped = 0, 0
for ts, path in images:
    frame = cv2.imread(path)
    if not is_valid_frame(frame):
        print(f"⚠️ Skipping bad frame: {path}")
        skipped += 1
        continue
    frame = cv2.resize(frame, (width, height))
    out.write(frame)
    used += 1

out.release()
print(f"✅ Timelapse saved as {OUTPUT_VIDEO}")
print(f"✅ Used {used} frames, skipped {skipped} bad frames.")
