import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIVE_MIN_DIR = os.path.join(ROOT_DIR, "images", "5min")
DAILY_DIR = os.path.join(ROOT_DIR, "images", "daily")
ARCHIVED_10MIN_DIR = os.path.join(ROOT_DIR, "images", "archived", "10min") 
ARCHIVED_INBETWEEN_DIR = os.path.join(ROOT_DIR, "images", "archived", "inbetween")
TIMELAPSE_DIR = os.path.join(ROOT_DIR, "timelapses")
ALL_CAPTURE_DIRS = [FIVE_MIN_DIR, DAILY_DIR, ARCHIVED_10MIN_DIR, ARCHIVED_INBETWEEN_DIR]

for d in ALL_CAPTURE_DIRS + [TIMELAPSE_DIR]:
    os.makedirs(d, exist_ok=True)