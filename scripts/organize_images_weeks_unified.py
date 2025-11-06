#!/usr/bin/env python3
"""
Organize ALL images into /images/Week XX - DD-DDmmm folders.

- Source roots: /images (anywhere inside) and /images_5min
- Destination:  /images/Week NN - <Mon..Sun range>/
- Monday-start ISO weeks; Europe/Madrid local time.
- Respects files already in the correct week folder.
- Safe to re-run (idempotent). Writes a simple audit in /images/.
"""

import re, time, shutil, subprocess
from pathlib import Path
from datetime import datetime, timedelta
import pytz

# ---------- Config ----------
TIMEZONE = "Europe/Madrid"
TZ = pytz.timezone(TIMEZONE)

IMAGES_ROOT = Path("images")
SOURCE_DIRS = [
    Path("images"),       # includes existing weekly folders and any loose files
    Path("images_5min"),  # legacy folder to keep in sync
]

EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff", ".bmp"}

# Accept timestamps like YYYYMMDD_HHMMSS or YYMMDD_HHMMSS in the filename
PAT_8 = re.compile(r"(\d{8}_\d{6})")  # 20251025_142015
PAT_6 = re.compile(r"(\d{6}_\d{6})")  # 251025_142015


def extract_tsYY(name: str):
    """Return YYMMDD_HHMMSS (string) or None."""
    m = PAT_8.search(name)
    if m:
        d, t = m.group(1).split("_")
        return f"{d[2:4]}{d[4:6]}{d[6:8]}_{t}"
    m = PAT_6.search(name)
    if m:
        return m.group(1)
    return None


def tsYY_to_utc(tsYY: str) -> datetime:
    """Assume filenames are UTC; map to 20YY."""
    YY, MM, DD = tsYY[:2], tsYY[2:4], tsYY[4:6]
    hh, mm, ss = tsYY[7:9], tsYY[9:11], tsYY[11:13]
    year = 2000 + int(YY)
    return datetime(year, int(MM), int(DD), int(hh), int(mm), int(ss))


def to_local(utc_dt: datetime) -> datetime:
    return pytz.utc.localize(utc_dt).astimezone(TZ)


def week_label(local_dt: datetime) -> str:
    """ISO week (Mon start). Label range Mon..Sun as DD-DDmmm or DDmmm-DDmmm if spanning months."""
    iso_year, iso_week, iso_weekday = local_dt.isocalendar()  # Mon=1
    monday = local_dt - timedelta(days=iso_weekday - 1)
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
        subprocess.run(["git", "mv", "-k", str(src), str(dst)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        return False


def move_file(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not git_mv(src, dst):
        shutil.move(str(src), str(dst))


def already_in_correct_week(p: Path, expected_week: str) -> bool:
    try:
        rel = p.relative_to(IMAGES_ROOT)
    except ValueError:
        return False
    return len(rel.parts) >= 2 and rel.parts[0] == expected_week


def organize():
    IMAGES_ROOT.mkdir(parents=True, exist_ok=True)

    # Gather candidate image files from sources
    candidates = []
    for root in SOURCE_DIRS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in EXTS:
                continue
            if ".git" in p.parts or "timelapses" in p.parts:
                continue
            candidates.append(p)

    # De-duplicate by absolute path
    uniq = {str(p.resolve()): p for p in candidates}
    files = sorted(uniq.values())

    moved, unchanged, skipped = [], [], []

    for p in files:
        tsYY = extract_tsYY(p.name)
        if not tsYY:
            skipped.append((str(p), "no timestamp in name"))
            continue

        utc_dt = tsYY_to_utc(tsYY)
        local_dt = to_local(utc_dt)
        wk = week_label(local_dt)

        # If already in correct /images/Week ...
        if already_in_correct_week(p, wk):
            unchanged.append(str(p))
            continue

        dest_dir = IMAGES_ROOT / wk
        dest = dest_dir / p.name

        # Collision-safe
        if dest.exists():
            base, ext = p.stem, p.suffix.lower()
            i = 1
            while (dest_dir / f"{base}_{i}{ext}").exists():
                i += 1
            dest = dest_dir / f"{base}_{i}{ext}"

        move_file(p, dest)
        moved.append((str(p), str(dest)))

    # Audit
    TS = time.strftime("%Y%m%d_%H%M%S")
    audit = IMAGES_ROOT / f"organize_weeks_audit_{TS}.txt"
    with open(audit, "w", encoding="utf-8") as f:
        f.write("ORGANIZE IMAGES BY WEEK (UNIFIED)\n")
        f.write(f"UTC run: {TS}\n\n")
        f.write(f"Total scanned: {len(files)}\n")
        f.write(f"Moved: {len(moved)}\n")
        f.write(f"Unchanged (already correct): {len(unchanged)}\n")
        f.write(f"Skipped (no timestamp): {len(skipped)}\n\n")
        if moved:
            f.write("== MOVED ==\n")
            for s, d in moved[:1000]:
                f.write(f"{s} -> {d}\n")
            f.write("\n")
        if unchanged:
            f.write("== UNCHANGED ==\n")
            for u in unchanged[:1000]:
                f.write(f"{u}\n")
            f.write("\n")
        if skipped:
            f.write("== SKIPPED ==\n")
            for s, why in skipped[:1000]:
                f.write(f"{s}  ({why})\n")
    print(f"✅ Audit: {audit}")
    print(f"Moved {len(moved)}, unchanged {len(unchanged)}, skipped {len(skipped)}")


if __name__ == "__main__":
    organize()
