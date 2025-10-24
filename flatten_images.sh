#!/usr/bin/env bash
set -euo pipefail

# ✅ Codespaces-friendly flattener
# Only operates under ./images/** — root files are untouched.

ROOT_DIR="$(pwd)"
IMAGES_DIR="$ROOT_DIR/images"

# Change to false to actually move files
DRY_RUN=true

# Also remove now-empty subdirectories under /images after moves
DELETE_EMPTY_DIRS=false

# Extensions to include (case-insensitive)
EXTS=(-iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.webp" -o -iname "*.tif" -o -iname "*.tiff")

echo "📂 Working dir: $ROOT_DIR"
echo "🎯 Target images dir: $IMAGES_DIR"
echo "🧪 DRY_RUN: $DRY_RUN"
echo "🧹 DELETE_EMPTY_DIRS: $DELETE_EMPTY_DIRS"
echo

# Ensure /images exists
mkdir -p "$IMAGES_DIR"

# Find images only inside /images subfolders (mindepth 2 = exclude files already at /images/*)
echo "🔎 Scanning /images for nested images..."
mapfile -t FILES < <(find "$IMAGES_DIR" -mindepth 2 -type f \( "${EXTS[@]}" \) -print || true)

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "✅ No nested images found under /images. Nothing to do."
  exit 0
fi

echo "📦 Found ${#FILES[@]} file(s) to flatten."
echo

move_one () {
  local src="$1"
  local base="$(basename "$src")"
  local dest="$IMAGES_DIR/$base"

  # Handle name collisions by appending parent + increment
  if [[ -e "$dest" ]]; then
    local parent="$(basename "$(dirname "$src")")"
    local name="${base%.*}"
    local ext="${base##*.}"
    local i=1
    while [[ -e "$IMAGES_DIR/${name}_${parent}_${i}.${ext}" ]]; do
      ((i++))
    done
    dest="$IMAGES_DIR/${name}_${parent}_${i}.${ext}"
  fi

  if [[ "$DRY_RUN" == true ]]; then
    echo "DRY-RUN: would move  $src  ->  $dest"
  else
    if command -v git >/dev/null 2>&1; then
      git mv -k "$src" "$dest" 2>/dev/null || mv "$src" "$dest"
    else
      mv "$src" "$dest"
    fi
    echo "✅ moved: $src -> $dest"
  fi
}

for f in "${FILES[@]}"; do
  move_one "$f"
done

if [[ "$DELETE_EMPTY_DIRS" == true ]]; then
  echo
  if [[ "$DRY_RUN" == true ]]; then
    echo "DRY-RUN: would delete now-empty subdirectories under /images"
  else
    # Remove empty subdirs (leaves /images itself)
    find "$IMAGES_DIR" -mindepth 1 -type d -empty -print -delete || true
    echo "🧹 Removed empty subdirectories under /images"
  fi
fi

echo
if [[ "$DRY_RUN" == true ]]; then
  echo "🧪 DRY RUN complete."
  echo "👉 To apply changes: edit flatten_images.sh and set DRY_RUN=false (and optionally DELETE_EMPTY_DIRS=true), then rerun:"
  echo "   ./flatten_images.sh"
  echo "   git add -A && git commit -m 'Flatten images into /images' && git push"
else
  echo "✅ Moves complete."
  echo "Next:"
  echo "   git add -A && git commit -m 'Flatten images into /images' && git push"
fi
