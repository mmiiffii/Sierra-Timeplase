import cv2
import os
from glob import glob
from datetime import datetime

# === Config ===
FOLDERS = ["images_10min", "images_inbetween"]
OUTPUT_VIDEO = f"timelapse_combined_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
FPS = 24

# Collect all images from both folders
images = []
for folder in FOLDERS:
    images.extend(glob(os.path.join(folder, "*.jpg")))

# Sort by filename (which contains UTC timestamp)
images = sorted(images)

if not images:
    raise ValueError("❌ No images found in either folder!")

# Read first image to get dimensions
frame = cv2.imread(images[0])
height, width, _ = frame.shape

# Define codec and create VideoWriter
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (width, height))

print(f"🎬 Creating 24fps timelapse with {len(images)} frames...")

for img_file in images:
    frame = cv2.imread(img_file)
    if frame is None:
        print(f"⚠️ Skipping unreadable file: {img_file}")
        continue
    resized = cv2.resize(frame, (width, height))
    out.write(resized)

out.release()
print(f"✅ Timelapse saved as {OUTPUT_VIDEO}")
