#!/bin/bash
# Render all three onboarding-video compositions (DESIGN.md-restyled) and concat.
# --low-memory-mode: pins 1 worker + screenshot capture (host has only ~1.1GB free RAM).
set -e
export HYPERFRAMES_BROWSER_PATH=/mnt/d/start-dev-video/.hf-cache/chs-wrapper.sh
export HYPERFRAMES_FFMPEG_PATH=/usr/bin/ffmpeg
export HYPERFRAMES_FFPROBE_PATH=/usr/bin/ffprobe
export HYPERFRAMES_EXTRACT_CACHE_DIR=/mnt/d/Alsini-physics-platform/.hf-cache/extract-tmp
cd /home/alsuni/Alsini-physics-platform/onboarding-video
mkdir -p dist
echo "[render] index.html -> dist/index.mp4"
hyperframes render -o dist/index.mp4 --low-memory-mode    > dist/render-index.log 2>&1
echo "[render] part2 -> dist/part2.mp4"
hyperframes render --composition compositions/part2.html -o dist/part2.mp4 --low-memory-mode > dist/render-part2.log 2>&1
echo "[render] part3 -> dist/part3.mp4"
hyperframes render --composition compositions/part3.html -o dist/part3.mp4 --low-memory-mode > dist/render-part3.log 2>&1
echo "[concat] -> dist/final.mp4"
printf "file '%s'\nfile '%s'\nfile '%s'\n" \
  "/home/alsuni/Alsini-physics-platform/onboarding-video/dist/index.mp4" \
  "/home/alsuni/Alsini-physics-platform/onboarding-video/dist/part2.mp4" \
  "/home/alsuni/Alsini-physics-platform/onboarding-video/dist/part3.mp4" > dist/concat.txt
/usr/bin/ffmpeg -y -f concat -safe 0 -i dist/concat.txt -c copy dist/final.mp4 > dist/concat.log 2>&1
echo "[done]"
echo "=== SIZES ==="; ls -lh dist/*.mp4
echo "=== DURATIONS ==="
for f in dist/index.mp4 dist/part2.mp4 dist/part3.mp4 dist/final.mp4; do
  printf "%s: " "$f"; /usr/bin/ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$f"
done
echo "=== FINAL VIDEO STREAMS ==="; /usr/bin/ffprobe -v error -show_entries stream=codec_type,codec_name,width,height -of compact dist/final.mp4
echo "RENDER_SCRIPT_DONE"