#!/usr/bin/env python3
"""
Last 7 days timelapse with evenly spaced frame selection.

Sources:
  - images/**       (weekly folders etc.)
  - images_5min/    (legacy folder at repo root)

Window:
  - last full 7 days, starting 250 minutes before sunrise on the earliest day
Output:
  - timelapses/timelapse_last7days_<startLocal>_<endUTC>_<fps>fps.mp4
"""

import os, re, sys, argparse
from glob import glob
from pathlib import Path
from datetime import datetime, timedelta, time

import cv2
import numpy as np

# ---- Location (Pradollano, Sierra Nevada) ----
LOCATION_NAME = "Pradollano"
REGION_NAME   = "Spain"
LATITUDE      = 37.0870
LONGITUDE     = -3.3920
TIMEZONE      = "Europe/Madrid"
MINUTES_BEFORE_SUNRISE = 250

# ---- Inputs (folders) ----
IMAGES_ROOT = Path("images")
LEGACY_5MIN = Path("images_5min")
OUTPUT_DIR  = Path("timelapses")

# ---- Filename timestamp patterns ----
PAT_8 = re.compile(r"(\d{8}_\d{6})")  # 20251025_142015
PAT_6 = re.compile(r"(\d{6}_\d{6})")  # 251025_142015

# ---- Bad-frame detection thresholds ----
MIN_DIM = 100
MIN_STD = 8
BLACK_LEVEL = 15
WHITE_LEVEL = 240
PERCENT_BLACK = 0.55
PERCENT_WHITE = 0.55
DOMINANT_BIN_RATIO = 0.55
HALF_DIFF_THRESH = 60
LAPL_VAR_MAX = 1e6

def extract_ts_from_name(name: str):
    """Return ts in YYMMDD_HHMMSS or None."""
    m = PAT_8.search(name)
    if m:
        date8, time6 = m.group(1).split("_")
        yy = date8[2:4]; mm = date8[4:6]; dd = date8[6:8]
        return f"{yy}{mm}{dd}_{time6}"
    m = PAT_6.search(name)
    if m:
        return m.group(1)
    return None

def ts_to_datetime_utc(tsYY: str) -> datetime:
    """Assume filenames are UTC. YYMMDD_HHMMSS -> naive UTC datetime (2000-2099)."""
    YY,MM,DD = tsYY[:2], tsYY[2:4], tsYY[4:6]
    hh,mm,ss = tsYY[7:9], tsYY[9:11], tsYY[11:13]
    year = 2000 + int(YY)
    return datetime(year, int(MM), int(DD), int(hh), int(mm), int(ss))

def gather_images():
    """Return sorted list of (utc_dt, path) from /images/** and /images_5min/*."""
    exts = {".jpg",".jpeg",".png",".webp",".bmp",".tif",".tiff"}
    items = []

    if IMAGES_ROOT.exists():
        for p in IMAGES_ROOT.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                tsYY = extract_ts_from_name(p.name)
                if tsYY:
                    items.append((ts_to_datetime_utc(tsYY), p))

    if LEGACY_5MIN.exists():
        for p in LEGACY_5MIN.iterdir():
            if p.is_file() and p.suffix.lower() in exts:
                tsYY = extract_ts_from_name(p.name)
                if tsYY:
                    items.append((ts_to_datetime_utc(tsYY), p))

    items.sort(key=lambda x: x[0])
    return items

def is_bad_frame(frame):
    """Return (True, reason) if frame is obviously bad."""
    if frame is None:
        return True, "unreadable"
    h, w = frame.shape[:2]
    if h < MIN_DIM or w < MIN_DIM:
        return True, f"too_small({w}x{h})"
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    std = float(np.std(gray))
    if std < MIN_STD:
        return True, f"low_std({std:.2f})"
    total = h*w
    black_ratio = float(np.sum(gray <= BLACK_LEVEL)) / total
    white_ratio = float(np.sum(gray >= WHITE_LEVEL)) / total
    if black_ratio >= PERCENT_BLACK:
        return True, f"mostly_black({black_ratio:.2f})"
    if white_ratio >= PERCENT_WHITE:
        return True, f"mostly_white({white_ratio:.2f})"
    hist = cv2.calcHist([gray],[0],None,[256],[0,256]).flatten()
    dom = float(hist.max()) / total
    if dom >= DOMINANT_BIN_RATIO:
        return True, f"dominant_bin({dom:.2f})"
    left_mean  = float(np.mean(gray[:, :w//2]))
    right_mean = float(np.mean(gray[:, w//2:]))
    if abs(left_mean - right_mean) > HALF_DIFF_THRESH:
        if left_mean <= (BLACK_LEVEL + 10) or right_mean <= (BLACK_LEVEL + 10):
            return True, "half_blank"
        if left_mean >= (WHITE_LEVEL - 10) or right_mean >= (WHITE_LEVEL - 10):
            return True, "half_white"
    lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if lap > LAPL_VAR_MAX:
        return True, f"excessive_lap({lap:.0f})"
    return False, ""

def compute_window_utc(images):
    """Compute (start_utc, end_utc, start_local) for last full 7 days with sunrise lead-in."""
    from astral import LocationInfo
    from astral.sun import sun
    import pytz

    if not images:
        raise RuntimeError("No images available to compute window.")

    tz = pytz.timezone(TIMEZONE)
    now_local = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(tz)
    earliest_day = (now_local.date() - timedelta(days=7))
    loc = LocationInfo(LOCATION_NAME, REGION_NAME, TIMEZONE, LATITUDE, LONGITUDE)
    s = sun(loc.observer, date=earliest_day, tzinfo=loc.timezone)
    sunrise_local = s.get("sunrise") or datetime.combine(earliest_day, time(6,0)).replace(tzinfo=tz)
    start_local = sunrise_local - timedelta(minutes=MINUTES_BEFORE_SUNRISE)
    start_utc = start_local.astimezone(pytz.utc).replace(tzinfo=None)
    end_utc = max(ts for ts,_ in images)  # latest available
    return start_utc, end_utc, start_local

def round_up_to_step(dt: datetime, step_minutes: int) -> datetime:
    """Round up to the next real-clock boundary where minute % step == 0, seconds == 0."""
    secs = step_minutes * 60
    epoch = int(dt.timestamp())
    rem = epoch % secs
    if rem == 0 and dt.second == 0:
        return dt.replace(second=0, microsecond=0)
    rounded = epoch + (secs - rem)
    return datetime.fromtimestamp(rounded).replace(second=0, microsecond=0)

def build_grid(start_utc: datetime, end_utc: datetime, step_minutes: int):
    """Generate evenly spaced UTC datetimes aligned to real clock boundaries."""
    grid = []
    t = round_up_to_step(start_utc, step_minutes)
    while t <= end_utc:
        grid.append(t)
        t += timedelta(minutes=step_minutes)
    return grid

def select_closest_per_grid(grid, candidates, tolerance_sec: int):
    """
    candidates: sorted list of (ts, path)
    For each grid time, pick the closest candidate within tolerance.
    Tie-breaker: earlier frame wins.
    """
    selected = []
    n = len(candidates)
    j = 0
    for g in grid:
        # advance j so that candidates[j] is the first with ts >= g - tolerance
        lower = g - timedelta(seconds=tolerance_sec)
        upper = g + timedelta(seconds=tolerance_sec)
        while j < n and candidates[j][0] < lower:
            j += 1
        # consider j-1, j, j+1 around g
        best = None
        for k in (j-1, j, j+1):
            if 0 <= k < n:
                ts, p = candidates[k]
                if ts < lower or ts > upper:
                    continue
                diff = abs((ts - g).total_seconds())
                if best is None or diff < best[0] or (diff == best[0] and ts < best[1]):
                    best = (diff, ts, p)
        if best is not None:
            selected.append((best[1], best[2]))
    # remove duplicates if two grids picked same file (rare)
    dedup = []
    seen_paths = set()
    for ts, p in selected:
        if p not in seen_paths:
            dedup.append((ts, p))
            seen_paths.add(p)
    return dedup

def main():
    ap = argparse.ArgumentParser(description="Last 7 days timelapse with evenly spaced selection.")
    ap.add_argument("--step-mins", type=int, default=5, help="Grid spacing in minutes (default: 5).")
    ap.add_argument("--tolerance-seconds", type=int, default=None,
                    help="Max allowed deviation from grid time in seconds (default: step/2).")
    ap.add_argument("--fps", type=int, default=24, help="Output frames per second.")
    args = ap.parse_args()

    step = max(1, args.step_mins)
    tol = args.tolerance_seconds if args.tolerance_seconds is not None else max(1, step*30)  # half step in seconds
    fps = max(1, args.fps)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = gather_images()
    if not images:
        print("No images found under /images/** or /images_5min")
        return 1

    start_utc, end_utc, start_local = compute_window_utc(images)
    window = [(ts,p) for ts,p in images if start_utc <= ts <= end_utc]
    if not window:
        print("No images within the computed 7-day window.")
        return 1

    # Build grid and select closest frames
    grid = build_grid(start_utc, end_utc, step)
    selected = select_closest_per_grid(grid, window, tol)
    if not selected:
        print("No frames matched the grid within tolerance.")
        return 1

    # Initialize writer using first good frame
    first = None
    for _, p in selected:
        f = cv2.imread(str(p))
        bad,_ = is_bad_frame(f)
        if not bad:
            first = f
            break
    if first is None:
        print("No valid frames after filtering bad ones.")
        return 1

    h,w = first.shape[:2]
    out_name = f"timelapse_last7days_{start_local.strftime('%Y%m%d_%H%M%S')}_{end_utc.strftime('%Y%m%d_%H%M%S')}_{fps}fps.mp4"
    out_path = OUTPUT_DIR / out_name
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w,h))

    used = skipped = 0
    used_times = []

    for ts, p in selected:
        f = cv2.imread(str(p))
        bad, why = is_bad_frame(f)
        if bad:
            skipped += 1
            continue
        if f.shape[:2] != (h,w):
            f = cv2.resize(f, (w,h))
        writer.write(f)
        used += 1
        used_times.append(ts)

    writer.release()

    if used == 0:
        print("No usable frames after filtering.")
        return 1

    print(f"Saved {out_path}")
    print(f"Used {used} frames, skipped {skipped} bad frames.")
    print(f"Grid step: {step} min, tolerance: {tol} sec, FPS: {fps}")
    print(f"Frame range (UTC): {min(used_times).isoformat()} -> {max(used_times).isoformat()}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
