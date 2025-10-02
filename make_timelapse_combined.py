import cv2
import os
from glob import glob
from datetime import datetime

# === Config ===
FOLDERS = ["images_10min", "images_inbetween"]
OUTPUT_DIR = "timelapses"
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_VIDEO = os.path.join(
    OUTPUT_DIR, f"timelapse_combined_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
)
FPS = 24

def extract_timestamp(path: str) -> datetime:
    """
    Extract timestamp from filenames like:
      - image_20250922_120000.jpg
      - inbetween_20250922_120500.jpg
    """
    base = os.path.basename(path)
    parts = base.split("_")
    if len(parts) < 3:
        return datetime.min
    try:
        return datetime.strptime(parts[1] + "_" + parts[2].split(".")[0], "%Y%m%d_%H%M%S")
    except ValueError:
        return datetime.min

# Collect all images with timestamps
images = []
for folder in FOLDERS:
    for f in glob(os.path.join(folder, "*.jpg")):
        ts = extract_timestamp(f)
        images.append((ts, f))

# Sort by timestamp
images = sorted(images, key=lambda x: x[0])

if not images:
    raise ValueError("❌ No images found in either folder!")

# Read first image to get frame size
frame = cv2.imread(images[0][1])
if frame is None:
    raise ValueError(f"❌ Could not read first image: {images[0][1]}")
height, width, _ = frame.shape

# Create video writer
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (width, height))

print(f"🎬 Creating 24fps timelapse with {len(images)} frames...")

# Add frames in order
for ts, img_file in images:
    frame = cv2.imread(img_file)
    if frame is None:
        print(f"⚠️ Skipping unreadable file: {img_file}")
        continue
    resized = cv2.resize(frame, (width, height))
    out.write(resized)

out.release()
print(f"✅ Timelapse saved as {OUTPUT_VIDEO}")
