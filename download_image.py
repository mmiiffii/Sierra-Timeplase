import os
import requests
from datetime import datetime

# Camera image URL
IMAGE_URL = "https://recursos.sierranevada.es/_extras/fotos_camaras/pradollano/snap_c1.jpg"
SAVE_FOLDER = "images"

# Create folder if it doesn't exist
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Generate a timestamped filename
timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
filename = os.path.join(SAVE_FOLDER, f"image_{timestamp}.jpg")

# Download image
try:
    response = requests.get(IMAGE_URL, timeout=30)
    response.raise_for_status()
    with open(filename, "wb") as f:
        f.write(response.content)
    print(f"✅ Saved {filename}")
except Exception as e:
    print(f"❌ Error downloading image: {e}")
