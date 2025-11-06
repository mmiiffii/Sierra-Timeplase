#!/usr/bin/env python3
"""
Organize Pradollano & Borreguiles images into weekly folders.
- Keeps them separate: /images/pradollano/... and /images/borreguiles/...
- Each uses Monday-start ISO week, Europe/Madrid local time.
- Safe to re-run any time.
"""
import os, re, csv, time, shutil, subprocess
from pathlib import Path
from datetime import datetime, timedelta
import pytz

TIMEZONE = "Europe/Madrid"
TZ = pytz.timezone(TIMEZONE)

DEST_ROOT = Path("images")
DEST_PRADO = DEST_ROOT / "pradollano"
DEST_BORRE = DEST_ROOT / "borreguiles"
for d in (DEST_PRADO, DEST_BORRE):
    d.mkdir(parents=True, exist_ok=True)

SOURCE_DIRS = [
    Path("images_pradollano"),
    Path("images_Borrguiles_5min"),
    Path("images_5min"),
    Path("images"),
]

EXTS = {".jpg",".jpeg",".png",".gif",".webp",".tif",".tiff",".bmp"}
PAT_8 = re.compile(r"(\d{8}_\d{6})")
PAT_6 = re.compile(r"(\d{6}_\d{6})")

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
    iso_year, iso_week, iso_weekday = local_dt.isocalendar()
    monday = local_dt - timedelta(days=iso_weekday-1)
    monday = datetime(monday.year, monday.month, monday.day, tzinfo=local_dt.tzinfo)
    sunday = monday + timedelta(days=6)
    def d_label(d): return f"{d.day:02d}{d.strftime('%b')}"
    if monday.month == sunday.month:
        rng = f"{monday.day:02d}-{sunday.day:02d}{monday.strftime('%b')}"
    else:
        rng = f"{d_label(monday)}-{d_label(sunday)}"
    return f"Week {iso_week:02d} - {rng}"

def which_camera(p: Path) -> str | None:
    parts = [x.lower() for x in p.parts]
    name = p.name.lower()
    if "images_pradollano" in parts or "images_5min" in parts or name.startswith("image_prado_"):
        return "prado"
    if "images_borrguiles_5min" in parts or name.startswith("image_borre_"):
        return "borre"
    return None

def dest_root_for_camera(cam: str) -> Path:
    return DEST_PRADO if cam == "prado" else DEST_BORRE

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
            if not p.is_file() or p.suffix.lower() not in EXTS:
                continue
            if ".git" in p.parts or "timelapses" in p.parts:
                continue
            all_files.append(p)

    uniq = {str(p.resolve()): p for p in all_files}
    files = sorted(uniq.values())

    moved, unchanged, skipped = [], [], []

    for p in files:
        cam = which_camera(p)
        if cam not in ("prado","borre"):
            skipped.append((str(p), "unknown camera"))
            continue
        tsYY = extract_tsYY(p.name)
        if not tsYY:
            skipped.append((str(p), "no timestamp"))
            continue
        utc_dt = tsYY_to_utc(tsYY)
        local_dt = to_local(utc_dt)
        wk = week_label(local_dt)

        dest_dir = dest_root_for_camera(cam) / wk
        dest = dest_dir / p.name
        if dest.exists():
            base, ext = p.stem, p.suffix.lower()
            i = 1
            while (dest_dir / f"{base}_{i}{ext}").exists():
                i += 1
            dest = dest_dir / f"{base}_{i}{ext}"

        # Skip if already correct
        try:
            rel = p.relative_to(dest_root_for_camera(cam))
            if rel.parts and rel.parts[0] == wk:
                unchanged.append(str(p))
                continue
        except ValueError:
            pass

        move_file(p, dest)
        moved.append((str(p), str(dest)))

    # Audit
    TS = time.strftime("%Y%m%d_%H%M%S")
    audit_txt = DEST_ROOT / f"organize
