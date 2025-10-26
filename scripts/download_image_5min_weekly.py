#!/usr/bin/env python3
import os
import requests
from pathlib import Path
from datetime import datetime, timedelta

# --- Config ---
IMAGE_URL = "https://recursos.sierranevada.es/_extras/fotos_camaras/pradollano/snap_c1.jpg"

# Timezone used for week bucketing and folder labels
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")

# If you also want a copy in /images/5min (in addition to the weekly folder), set env MIRROR_TO_5MIN="true"
MIRROR_TO_5MIN = os.getenv("MIRROR_TO_5MIN", "false").lower() in ("1", "true", "yes")

# --- Paths ---
IMAGES_ROOT = Path("images")
FIVE_MIN_DIR = IMAGES_ROOT / "5min"      # only used if MIRROR_TO_5MIN is true
IMAGES_ROOT.mkdir(parents=True, exist_ok=True)
if MIRROR_TO_5MIN:
    FIVE_MIN_DIR.mkdir(parents=True, exist_ok=True)

# --- TZ helpers ---
try:
    import pytz
except Exception:
    raise SystemExit("Please add 'pytz' to requirements.txt for timezone handling.")

def now_utc():
    return datetime.utcnow().replace(microsecond=0)

def to_local(dt_utc):
    tz = pytz.timezone(TIMEZONE)
    return pytz.utc.localize(dt_utc).astimezone(tz)

def week_folder_for(local_dt: datetime) -> str:
    """
    Build label like:
      - Week 07 - 12-18Feb   (same month)
      - Week 08 - 26Feb-03Mar (spans months)
    Monday is the first day of week.
    """
    iso_year, iso_week, iso_weekday = local_dt.isocalendar()  # Monday=1..Sunday=7
    monday = local_dt - timedelta(days=iso_weekday - 1)
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6)

    def d_label(d: datetime) -> str:
        return f"{d.day:02d}{d.strftime('%b')}"

    if monday.month == sunday.month:
        range_label = f"{monday.day:02d}-{sunday.day:02d}{monday.strftime('%b')}"
    else:
        range_label = f"{d_label(monday)}-{d_label(sunday)}"

    return f"Week {iso_week:02d} - {range_label}"

def make_filename(dt_utc: datetime, ext: str) -> str:
    # YYMMDD_HHMMSS format
    return f"image_{dt_utc.strftime('%y%m%d_%H%M%S')}{ext.lower()}"

def save_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

def main():
    # 1) Download image
    try:
        r = requests.get(IMAGE_URL, timeout=25)
        r.raise_for_status()
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return 1

    # 2) Decide destinations (weekly + optional 5min)
    ts_utc = now_utc()
    ts_local = to_local(ts_utc)
    folder_name = week_folder_for(ts_local)
    weekly_dir = IMAGES_ROOT / folder_name

    # Try to infer extension (default .jpg)
    ext = ".jpg"
    ct = r.headers.get("Content-Type", "").lower()
    if "png" in ct:
        ext = ".png"
    elif "jpeg" in ct or "jpg" in ct:
        ext = ".jpg"
    elif "webp" in ct:
        ext = ".webp"

    filename = make_filename(ts_utc, ext)
    weekly_path = weekly_dir / filename

    # Collision-safe (very unlikely, but safe)
    i = 1
    while weekly_path.exists():
        weekly_path = weekly_dir / f"{filename[:-len(ext)]}_{i}{ext}"
        i += 1

    # 3) Save
    save_bytes(weekly_path, r.content)
    print(f"✅ Saved {weekly_path}")

    if MIRROR_TO_5MIN:
        five_min_path = FIVE_MIN_DIR / filename
        j = 1
        while five_min_path.exists():
            five_min_path = FIVE_MIN_DIR / f"{filename[:-len(ext)]}_{j}{ext}"
            j += 1
        save_bytes(five_min_path, r.content)
        print(f"↪︎ Mirrored to {five_min_path}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
