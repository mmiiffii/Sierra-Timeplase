import os
import requests
from datetime import datetime

# === Config ===
IMAGE_URL = "https://recursos.sierranevada.es/_extras/fotos_camaras/pradollano/snap_c1.jpg"
SAVE_FOLDER = "images_inbetween"

# Ensure folder exists
if os.path.exists(SAVE_FOLDER) and not os.path.isdir(SAVE_FOLDER):
    os.remove(SAVE_FOLDER)
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Filename format matches the 10min script but with prefix 'inbetween'
timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
filename = os.path.join(SAVE_FOLDER, f"inbetween_{timestamp}.jpg")

try:
    response = requests.get(IMAGE_URL, timeout=30)
    response.raise_for_status()
    with open(filename, "wb") as f:
        f.write(response.content)
    print(f"✅ Saved {filename}")
except Exception as e:
    print(f"❌ Error downloading image: {e}")
