#!/bin/bash
set -e

# Move existing images
mv images_5min/* images/5min/ 2>/dev/null || true
mv images_10min/* images/archived/10min/ 2>/dev/null || true
mv images_inbetween/* images/archived/inbetween/ 2>/dev/null || true
mv images/* images/daily/ 2>/dev/null || true

# Cleanup old directories
rm -rf images_5min images_10min images_inbetween

# Git commands
git add .
git commit -m "Reorganize repository structure"
git push
