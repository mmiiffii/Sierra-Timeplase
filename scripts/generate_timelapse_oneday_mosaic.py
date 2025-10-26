#!/usr/bin/env python3
"""
Create a "composite day" timelapse:
- Order by local time-of-day from start (e.g., 05:00) to start+24h
- Pick each frame from *different* dates (never same day back-to-back)
- Evenly spaced grid (e.g. every 5 minutes), with tolerance window
- Sources: images/** and legacy images_5min/
- Output: timelapses/timelapse_oneday_<startHHMM>_<fps>fps.mp4
"""

import os, re, sys, argparse
from pathlib import Path
from datetime import datetime, timedelta, time as dtime
import cv2, numpy as np

# ---- Location / TZ ----
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")

# ---- Inputs / outputs ----
IMAGES_ROOT = Path("images")
LEGACY_5MIN = Path("images_5min")
OUTPUT_DIR  = Path("timelapses")

# ---- Filename timestamp patterns ----
PAT_8 = re.compile(r"(\d{8}_\d{6})")  # 20251025_142015
PAT_6 = re.compile(r"(\d{6}_\d{6})")  # 251025_142015

# ---- Bad-frame thresholds ----
MIN_DIM = 100
MIN_STD = 8
BLACK_LEVEL = 15
WHITE_LEVEL = 240
PERCENT_BLACK = 0.55
PERCENT_WHITE = 0.55
DOMINANT_BIN_RATIO = 0.55
HALF_DIFF_THRESH = 60
LAPL_VAR_MAX = 1e6

# ---- Helpers ----
def extract_ts_from_name(name: str):
    """Return YYMMDD_HHMMSS or None."""
    m = PAT_8.search(name)
    if m:
        date8, time6 = m.group(1).split("_")
        yy = date8[2:4]; mm = date8[4:6]; dd = date8[6:8]
        return f"{yy}{mm}{dd}_{time6}"
    m = PAT_6.search(name)
    if m:
        return m.group(1)
    return None

def tsYY_to_utc(tsYY: str) -> datetime:
    """Assume filenames are UTC. YYMMDD_HHMMSS -> naive UTC datetime (2000-2099)."""
    YY,MM,DD = tsYY[:2], tsYY[2:4], tsYY[4:6]
    hh,mm,ss = tsYY[7:9], tsYY[9:11], tsYY[11:13]
    year = 2000 + int(YY)
    return datetime(year, int(MM), int(DD), int(hh), int(mm), int(ss))

def to_local(utc_dt: datetime):
    import pytz
    tz = pytz.timezone(TIMEZONE)
    return pytz.utc.localize(utc_dt).astimezone(tz)

def seconds_since_midnight_local(local_dt: datetime) -> int:
    return local_dt.hour*3600 + local_dt.minute*60 + local_dt.second

def is_bad_frame(frame):
    if frame is None: return True, "unreadable"
    h,w = frame.shape[:2]
    if h < MIN_DIM or w < MIN_DIM: return True, f"too_small({w}x{h})"
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    std = float(np.std(gray))
    if std < MIN_STD: return True, f"low_std({std:.2f})"
    total = h*w
    black_ratio = float(np.sum(gray <= BLACK_LEVEL)) / total
    white_ratio = float(np.sum(gray >= WHITE_LEVEL)) / total
    if black_ratio >= PERCENT_BLACK: return True, f"mostly_black({black_ratio:.2f})"
    if white_ratio >= PERCENT_WHITE: return True, f"mostly_white({white_ratio:.2f})"
    hist = cv2.calcHist([gray],[0],None,[256],[0,256]).flatten()
    dom = float(hist.max())/total
    if dom >= DOMINANT_BIN_RATIO: return True, f"dominant_bin({dom:.2f})"
    left_mean  = float(np.mean(gray[:, :w//2]))
    right_mean = float(np.mean(gray[:, w//2:]))
    if abs(left_mean-right_mean) > HALF_DIFF_THRESH:
        if left_mean <= (BLACK_LEVEL+10) or right_mean <= (BLACK_LEVEL+10): return True, "half_blank"
        if left_mean >= (WHITE_LEVEL-10) or right_mean >= (WHITE_LEVEL-10): return True, "half_white"
    lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if lap > LAPL_VAR_MAX: return True, f"excessive_lap({lap:.0f})"
    return False, ""

def gather_images():
    """Return list of dicts: {utc, local, date_str, sod_sec, path} from images/** and images_5min/."""
    exts = {".jpg",".jpeg",".png",".webp",".bmp",".tif",".tiff"}
    items = []

    def add_path(p: Path):
        tsYY = extract_ts_from_name(p.name)
        if not tsYY: return
        utc_dt = tsYY_to_utc(tsYY)
        loc_dt = to_local(utc_dt)
        date_str = loc_dt.strftime("%Y-%m-%d")  # calendar day (local)
        items.append({
            "utc": utc_dt,
            "local": loc_dt,
            "date_str": date_str,
            "sod_sec": seconds_since_midnight_local(loc_dt),
            "path": p
        })

    if IMAGES_ROOT.exists():
        for p in IMAGES_ROOT.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                add_path(p)

    if LEGACY_5MIN.exists():
        for p in LEGACY_5MIN.iterdir():
            if p.is_file() and p.suffix.lower() in exts:
                add_path(p)

    # sort by local time-of-day, then by utc
    items.sort(key=lambda x: (x["sod_sec"], x["utc"]))
    return items

def build_tod_grid(start_local: dtime, step_minutes: int):
    """Return list of seconds-since-midnight for 24h from start."""
    grid = []
    total_sec = 24*3600
    step_sec = step_minutes*60
    start_sec = start_local.hour*3600 + start_local.minute*60 + start_local.second
    s = start_sec
    while len(grid)==0 or (s - start_sec) % total_sec != 0:
        grid.append(s % total_sec)
        s += step_sec
        if len(grid) > (24*60)//step_minutes + 10:  # safety
            break
    return grid

def select_frames_by_tod(grid_sods, items, tolerance_sec, forbid_consecutive_same_day=True):
    """
    For each time-of-day slot (seconds-of-day), pick closest frame across *any* day,
    within tolerance. If forbid_consecutive_same_day: never pick same date_str back-to-back.
    """
    # Build index by sod_sec
    by_sod = {}  # sod_sec -> list of items (sorted by |delta| later)
    for it in items:
        by_sod.setdefault(it["sod_sec"], []).append(it)

    selected = []
    last_day = None
    used_paths = set()

    # Prebuild a list of (candidate, abs_delta) for each grid slot by scanning nearby seconds
    # To keep it efficient, search within [sod - tol .. sod + tol]
    for sod in grid_sods:
        best = None
        best_not_last = None
        # Examine items whose sod_sec within tolerance
        lo = sod - tolerance_sec
        hi = sod + tolerance_sec

        # Iterate items and compute delta; this is O(N) but fine for repo-sized sets.
        for it in items:
            d = it["sod_sec"]
            # circular day wrap: compare against both d and d±86400 to get minimal wrap distance
            deltas = [abs(d - sod), abs((d + 86400) - sod), abs((d - 86400) - sod)]
            delta = min(deltas)
            if delta > tolerance_sec:
                continue
            if str(it["path"]) in used_paths:
                continue
            # prefer not same day as previous
            tup = (delta, it["utc"], it)  # tie-breaker by earlier utc
            if best is None or tup < best:
                best = tup
            if forbid_consecutive_same_day and it["date_str"] != last_day:
                if best_not_last is None or tup < best_not_last:
                    best_not_last = tup

        pick = best_not_last if (forbid_consecutive_same_day and best_not_last is not None) else best
        if pick is None:
            # no candidate for this slot
            continue
        _, _, it = pick
        selected.append(it)
        last_day = it["date_str"]
        used_paths.add(str(it["path"]))

    return selected

def main():
    ap = argparse.ArgumentParser(description="Composite 'one day' timelapse from many days by time-of-day.")
    ap.add_argument("--start", default="05:00", help="Local start time HH:MM (default 05:00)")
    ap.add_argument("--step-mins", type=int, default=5, help="Grid spacing minutes (default 5)")
    ap.add_argument("--tolerance-seconds", type=int, default=None, help="Max deviation from slot (default step/2)")
    ap.add_argument("--fps", type=int, default=24, help="Output FPS (default 24)")
    args = ap.parse_args()

    try:
        hh, mm = map(int, args.start.split(":"))
        start_local_time = dtime(hour=hh, minute=mm, second=0)
    except Exception:
        print("Invalid --start format. Use HH:MM, e.g. 05:00")
        return 2

    step = max(1, args.step_mins)
    tol = args.tolerance_seconds if args.tolerance_seconds is not None else max(1, step*30)  # half step
    fps = max(1, args.fps)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    items = gather_images()
    if not items:
        print("No images found in images/** or images_5min/")
        return 1

    grid = build_tod_grid(start_local_time, step)
    selected = select_frames_by_tod(grid, items, tolerance_sec=tol, forbid_consecutive_same_day=True)
    if not selected:
        print("No frames matched the grid within tolerance.")
        return 1

    # Initialize writer using first good frame
    first_frame = None
    first_w = first_h = None
    valid = []
    for it in selected:
        frame = cv2.imread(str(it["path"]))
        bad, _ = is_bad_frame(frame)
        if bad:
            continue
        if first_frame is None:
            first_frame = frame
            first_h, first_w = frame.shape[:2]
        valid.append((it, frame))

    if not valid:
        print("No valid frames after filtering.")
        return 1

    out_name = f"timelapse_oneday_{start_local_time.strftime('%H%M')}_{fps}fps.mp4"
    out_path = OUTPUT_DIR / out_name
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (first_w, first_h))

    used = skipped = 0
    for it, frame in valid:
        if frame.shape[:2] != (first_h, first_w):
            frame = cv2.resize(frame, (first_w, first_h))
        writer.write(frame)
        used += 1
    writer.release()

    skipped = len(selected) - used
    print(f"Saved {out_path}")
    print(f"Selected grid slots: {len(grid)}")
    print(f"Used frames: {used}, skipped (bad/tolerance): {skipped}")
    print(f"Start local: {start_local_time.strftime('%H:%M')}, step: {step} min, tolerance: {tol} sec, FPS: {fps}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
