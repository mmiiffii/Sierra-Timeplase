import cv2
import os
from glob import glob
from datetime import datetime

# === Configuration ===
IMAGE_FOLDER = "images_10min"
OUTPUT_VIDEO = f"timelapse_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
FPS = 12

# Get all jpg images sorted by filename (timestamp in name)
images = sorted(glob(os.path.join(IMAGE_FOLDER, "*.jpg")))

if not images:
    raise ValueError("❌ No images found in folder!")

# Read the first image to get dimensions
frame = cv2.imread(images[0])
height, width, _ = frame.shape

# Define the codec and create VideoWriter object
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (width, height))

print(f"🎬 Creating timelapse with {len(images)} frames at {FPS} fps...")

# Add each image to the video
for img_file in images:
    frame = cv2.imread(img_file)
    if frame is None:
        print(f"⚠️ Skipping unreadable file: {img_file}")
        continue
    resized = cv2.resize(frame, (width, height))  # ensure consistent size
    out.write(resized)

out.release()
print(f"✅ Timelapse saved as {OUTPUT_VIDEO}")
