#!/usr/bin/env python3
"""
Simplified weekly image organizer.
Moves all image_*.jpg style files into /images/Week XX - DD-DDmmm folders.
Uses Monday-start ISO weeks in Europe/Madrid local time.
"""
import os, re, time, shutil, subprocess
from pathlib import Path
from datetime import datetime, timedelta
import pytz

TIMEZONE = "Europe/Madrid"
TZ = pytz.timezone(TIMEZONE)

IMAGES_ROOT = Path("images")
SOURCE_DIRS = [
    Path("images"),
    Path("images_5min"),
    Path("images_pradollano"),
]

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
PAT_8 = re.compile(r"(\d{8}_\d{6})")  # 20251025_142015
PAT_6 = re.compile(r"(\d{6}_\d{6})")  # 251025_142015

def extract_tsYY(name: str):
    m = PAT_8.search(name)
    if m:
        d,t = m.group(1).split("_")
        return f"{d[2:4]}{d[4:6]}{d[6:8]}_{t}"
    m = PAT_6.search(name)
    if m:
        return m.group(1)
    return None

def tsYY_to_utc(tsYY: str) -> datetime:
    YY,MM,DD = tsYY[:2], tsYY[2:4], tsYY[4:6]
    hh,mm,ss = tsYY[7:9], tsYY[9:11], tsYY[11:13]
    year = 2000 + int(YY)
    return datetime(year, int(MM), int(DD), int(hh), int(mm), int(ss))

def to_local(utc_dt: datetime) -> datetime:
    return pytz.utc.localize(utc_dt).astimezone(TZ)

def week_label(local_dt: datetime) -> str:
    iso_year, iso_week, iso_weekday = local_dt.isocalendar()  # Monday=1
    monday = local_dt - timedelta(days=iso_weekday-1)
    monday = datetime(monday.year, monday.month, monday.day, tzinfo=local_dt.tzinfo)
    sunday = monday + timedelta(days=6)
    def d_label(d): return f"{d.day:02d}{d.strftime('%b')}"
    if monday.month == sunday.month:
        rng = f"{monday.day:02d}-{sunday.day:02d}{monday.strftime('%b')}"
    else:
        rng = f"{d_label(monday)}-{d_label(sunday)}"
    return f"Week {iso_week:02d} - {rng}"

def git_mv(src: Path, dst: Path) -> bool:
    try:
        subprocess.run(["git","mv","-k",str(src),str(dst)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        return False

def move_file(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not git_mv(src, dst):
        shutil.move(str(src), str(dst))

def organize():
    all_files = []
    for root in SOURCE_DIRS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file(): continue
            if p.suffix.lower() not in EXTS: continue
            if ".git" in p.parts or "timelapses" in p.parts: continue
            all_files.append(p)

    uniq = {str(p.resolve()): p for p in all_files}
    files = sorted(uniq.values())

    moved, unchanged, skipped = [], [], []

    for p in files:
        tsYY = extract_tsYY(p.name)
        if not tsYY:
            skipped.append((str(p), "no timestamp"))
            continue
        utc_dt = tsYY_to_utc(tsYY)
        local_dt = to_local(utc_dt)
        wk = week_label(local_dt)
        dest_dir = IMAGES_ROOT / wk
        dest = dest_dir / p.name

        # Skip if already correct
        try:
            rel = p.relative_to(IMAGES_ROOT)
            if rel.parts and rel.parts[0] == wk:
                unchanged.append(str(p))
                continue
        except ValueError:
            pass

        if dest.exists():
            base, ext = p.stem, p.suffix.lower()
            i = 1
            while (dest_dir / f"{base}_{i}{ext}").exists():
                i += 1
            dest = dest_dir / f"{base}_{i}{ext}"

        move_file(p, dest)
        moved.append((str(p), str(dest)))

    TS = time.strftime("%Y%m%d_%H%M%S")
    audit = IMAGES_ROOT / f"organize_simple_audit_{TS}.txt"
    with open(audit, "w", encoding="utf-8") as f:
        f.write(f"Run: {TS}\n\nMoved: {len(moved)}\nUnchanged: {len(unchanged)}\nSkipped: {len(skipped)}\n\n")
        for s,d in moved: f.write(f"MOVED {s} -> {d}\n")
        for u in unchanged: f.write(f"UNCHANGED {u}\n")
        for s,why in skipped: f.write(f"SKIPPED {s} ({why})\n")
    print(f"✅ Audit written: {audit}")
    print(f"Moved {len(moved)}, unchanged {len(unchanged)}, skipped {len(skipped)}")

if __name__ == "__main__":
    organize()
