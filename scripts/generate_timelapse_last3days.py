#!/usr/bin/env python3
"""
Generate a timelapse covering the last full 3 days, starting 5 minutes before sunrise
on the earliest of those days. Uses images from folders:
 - images_10min
 - images_inbetween
 - images_5min

Writes one MP4 to timelapses/timelapse_last3days_<start>_<end>_24fps.mp4
Prints summary: number of frames used and skipped.
"""

import os
import re
import sys
from glob import glob
from datetime import datetime, date, timedelta, time
import cv2
import numpy as np

# Astral for sunrise calculations
try:
    from astral import LocationInfo
    from astral.sun import sun
except Exception:
    print("Missing 'astral' dependency. Please ensure requirements.txt contains astral.")
    sys.exit(2)

# -------- CONFIG (edit if needed) --------
FOLDERS = ["images_10min", "images_inbetween", "images_5min"]
OUTPUT_DIR = "timelapses"
FPS = 24

# Location: Pradollano, Sierra Nevada (approx)
LOCATION_NAME = "Pradollano"
REGION_NAME = "Spain"
LATITUDE = 37.0870
LONGITUDE = -3.3920
TIMEZONE = "Europe/Madrid"

# How many minutes before sunrise to start
MINUTES_BEFORE_SUNRISE = 100

# Bad-frame detection thresholds (tweak if needed)
MIN_DIM = 100
MIN_STD = 8           # too-low std -> near-flat image
BLACK_LEVEL = 15
WHITE_LEVEL = 240
PERCENT_BLACK = 0.55
PERCENT_WHITE = 0.55
DOMINANT_BIN_RATIO = 0.55
HALF_DIFF_THRESH = 60
LAPL_VAR_MAX = 1e6

# Regex for timestamp in filename: YYYYmmdd_HHMMSS
TS_RE = re.compile(r'(\d{8}_\d{6})')

# -----------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_ts(path):
    m = TS_RE.search(os.path.basename(path))
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
    except Exception:
        return None

def gather_images():
    imgs = []
    for folder in FOLDERS:
        if not os.path.isdir(folder):
            continue
        for p in glob(os.path.join(folder, "*.jpg")):
            ts = extract_ts(p)
            if ts:
                imgs.append((ts, p))
    imgs.sort(key=lambda x: x[0])
    return imgs

def is_bad_frame(frame):
    """Return (True, reason) for bad frames."""
    if frame is None:
        return True, "unreadable"
    h, w = frame.shape[:2]
    if h < MIN_DIM or w < MIN_DIM:
        return True, f"too_small ({w}x{h})"
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = float(np.mean(gray))
    std = float(np.std(gray))
    # black / white masks
    black_ratio = float(np.sum(gray <= BLACK_LEVEL)) / (h * w)
    white_ratio = float(np.sum(gray >= WHITE_LEVEL)) / (h * w)
    if black_ratio >= PERCENT_BLACK:
        return True, f"mostly_black ({black_ratio:.2f})"
    if white_ratio >= PERCENT_WHITE:
        return True, f"mostly_white ({white_ratio:.2f})"
    if std < MIN_STD:
        return True, f"low_std ({std:.2f})"
    hist = cv2.calcHist([gray], [0], None, [256], [0,256]).flatten()
    dominant_ratio = float(np.max(hist)) / (h * w)
    if dominant_ratio >= DOMINANT_BIN_RATIO:
        return True, f"dominant_bin ({dominant_ratio:.2f})"
    left_mean = float(np.mean(gray[:, :w//2]))
    right_mean = float(np.mean(gray[:, w//2:]))
    if abs(left_mean - right_mean) > HALF_DIFF_THRESH:
        if left_mean <= (BLACK_LEVEL + 10) or right_mean <= (BLACK_LEVEL + 10):
            return True, f"half_blank (L={left_mean:.1f},R={right_mean:.1f})"
        if left_mean >= (WHITE_LEVEL - 10) or right_mean >= (WHITE_LEVEL - 10):
            return True, f"half_white (L={left_mean:.1f},R={right_mean:.1f})"
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if lap_var > LAPL_VAR_MAX:
        return True, f"excessive_lap_var ({lap_var:.1f})"
    return False, ""

def compute_start_end():
    """
    Determine the date range:
      - last full 3 days (in LOCATION timezone): day-1, day-2, day-3
      - start = sunrise(day-3) - MINUTES_BEFORE_SUNRISE
      - end = timestamp of the latest available image (max timestamp)
    """
    # location and timezone
    loc = LocationInfo(LOCATION_NAME, REGION_NAME, TIMEZONE, LATITUDE, LONGITUDE)

    # current date in location timezone
    now_utc = datetime.utcnow()
    # convert to location local date using astral/offset: simplest is take today's date in UTC then shift?
    # astral.sun requires date objects in local tz — we will compute 'today' as now in loc timezone:
    # Astral doesn't provide direct tz conversion here, but LocationInfo contains tz name; use datetime with tz info:
    try:
        import pytz
        tz = pytz.timezone(TIMEZONE)
        now_local = now_utc.replace(tzinfo=pytz.utc).astimezone(tz)
    except Exception:
        # fallback: assume UTC
        now_local = now_utc

    # last full day is yesterday in local date; we want the last 3 full days (yesterday, -2, -3)
    day_yesterday = (now_local.date() - timedelta(days=1))
    day_two = (now_local.date() - timedelta(days=2))
    day_three = (now_local.date() - timedelta(days=3))

    # compute sunrise for day_three (earliest day)
    s = sun(loc.observer, date=day_three, tzinfo=loc.timezone)
    sunrise_dt = s.get("sunrise")
    if sunrise_dt is None:
        # fallback to 06:00 local
        try:
            sunrise_dt = datetime.combine(day_three, time(6,0)).replace(tzinfo=tz)
        except Exception:
            sunrise_dt = datetime.combine(day_three, time(6,0))

    start_dt = sunrise_dt - timedelta(minutes=MINUTES_BEFORE_SUNRISE)

    return start_dt, day_three, day_yesterday

def main():
    images = gather_images()
    if not images:
        print("No images found in folders:", FOLDERS)
        return 1

    # compute start (sunrise of day_three minus minutes) and end (latest available)
    start_dt_local, day_three_date, day_yesterday_date = compute_start_end()
    # Convert start_dt_local to naive UTC datetime for comparing image filenames timestamps (filenames assumed UTC)
    # Our filenames are in UTC in previous scripts — if they are local, adjust accordingly.
    # Here we will convert start_dt_local to UTC naive
    try:
        import pytz
        tz = pytz.timezone(TIMEZONE)
        start_dt_utc = start_dt_local.astimezone(pytz.utc).replace(tzinfo=None)
    except Exception:
        # fallback: assume start_dt_local is UTC
        start_dt_utc = start_dt_local.replace(tzinfo=None)

    # End = latest available image timestamp
    latest_ts = max([ts for (ts, _) in images])

    # For user-friendly messaging print the date range we're using (local)
    print("Selected last full 3 days (local):", day_three_date.isoformat(), "->", day_yesterday_date.isoformat())
    print("Start (5 min before sunrise local):", start_dt_local.isoformat())
    print("Using images up to latest available:", latest_ts.isoformat())

    # Filter images between start_dt_utc and latest_ts (assuming filenames timestamps are UTC)
    candidates = [(ts, p) for (ts, p) in images if ts >= start_dt_utc and ts <= latest_ts]
    if not candidates:
        print("No candidate images found in the computed window. Start (UTC):", start_dt_utc.isoformat())
        return 1

    # Create output name using local start and latest
    outname = f"timelapse_last3days_{start_dt_local.strftime('%Y%m%d_%H%M%S')}_{latest_ts.strftime('%Y%m%d_%H%M%S')}_{FPS}fps.mp4"
    outpath = os.path.join(OUTPUT_DIR, outname)

    # remove existing mp4s starting with pattern to ensure single file per run
    for old in glob(os.path.join(OUTPUT_DIR, "timelapse_last3days_*.mp4")):
        try:
            os.remove(old)
        except Exception:
            pass

    # initialize video writer using first valid frame
    first_frame = None
    for ts, p in candidates:
        f = cv2.imread(p)
        bad, reason = is_bad_frame(f)
        if not bad:
            first_frame = f
            break
    if first_frame is None:
        print("Could not find any valid frames in the candidate window.")
        return 1

    height, width = first_frame.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(outpath, fourcc, FPS, (width, height))

    used = 0
    skipped = 0
    valid_times = []

    for ts, p in candidates:
        frame = cv2.imread(p)
        bad, reason = is_bad_frame(frame)
        if bad:
            print(f"Skipping {os.path.basename(p)} -> {reason}")
            skipped += 1
            continue
        if frame.shape[:2] != (height, width):
            frame = cv2.resize(frame, (width, height))
        out.write(frame)
        used += 1
        valid_times.append(ts)

    out.release()

    if used == 0:
        print("No usable frames after filtering.")
        return 1

    start_used = min(valid_times)
    end_used = max(valid_times)
    print(f"Saved {outpath}")
    print(f"Used {used} frames, skipped {skipped} bad frames.")
    print(f"Frame range used (UTC): {start_used.isoformat()} -> {end_used.isoformat()}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
