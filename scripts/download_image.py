import os
import requests
from datetime import datetime

# === Configuration ===
IMAGE_URL = "https://recursos.sierranevada.es/_extras/fotos_camaras/pradollano/snap_c1.jpg"
SAVE_FOLDER = "images"

# Ensure save folder exists and is a directory
if os.path.exists(SAVE_FOLDER) and not os.path.isdir(SAVE_FOLDER):
    os.remove(SAVE_FOLDER)
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Generate a unique filename with timestamp
timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
filename = os.path.join(SAVE_FOLDER, f"image_{timestamp}.jpg")

# Download the image
try:
    response = requests.get(IMAGE_URL, timeout=30)
    response.raise_for_status()
    with open(filename, "wb") as f:
        f.write(response.content)
    print(f"✅ Saved {filename}")
except Exception as e:
    print(f"❌ Error downloading image: {e}")
