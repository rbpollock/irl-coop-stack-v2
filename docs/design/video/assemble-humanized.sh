#!/usr/bin/env bash
# Assemble "Goodbye Group Gouging" — humanized NeuTTS narration (h- files) + closing slide.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p assembling
rm -f assembling/*.mp4 concat.txt

# closing slide -> static clip long enough for its VO
clen=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 vo/h-closing.mp3)
clen=$(python3 -c "print('%.3f' % (float('$clen') + 0.5))")
ffmpeg -y -v error </dev/null -loop 1 -i closing-slide.png \
  -vf "scale=1920:1080,format=yuv420p" -t "$clen" -r 24 \
  -c:v libx264 -preset fast -crf 22 assembling/closing-slide.mp4
echo "built closing-slide clip (${clen}s)"

# each content clip: hold last frame while its VO plays, padded to VO length + air
: > concat.txt
while IFS=: read -r clip vo; do
  vlen=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$vo")
  target=$(python3 -c "print('%.2f' % (float('$vlen') + 0.3))")
  out="assembling/$(basename "$clip")"
  echo "  $clip (→ ${target}s)"
  ffmpeg -y -v error </dev/null -i "$clip" -i "$vo" \
    -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=${vlen}[v];[1:a]apad=pad_dur=0.3[a]" \
    -map "[v]" -map "[a]" -t "$target" \
    -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p -c:a aac -b:a 128k "$out"
  echo "file '$out'" >> concat.txt
done <<'EOF'
title-clip.mp4:vo/h-title.mp3
cost-model-divergence.mp4:vo/h-divergence.mp3
cost-model-wall.mp4:vo/h-wall.mp3
cost-model-three-ways.mp4:vo/h-three.mp3
cost-model-per-participant.mp4:vo/h-participant.mp3
cost-model-redundancy.mp4:vo/h-redundancy.mp3
cost-model-crossover.mp4:vo/h-crossover.mp3
value-flow-diagram.mp4:vo/h-value.mp3
fear-loop-diagram.mp4:vo/h-fear.mp3
EOF

# closing slide clip + its VO muxed
target=$(python3 -c "print('%.2f' % (float('$clen') + 0.2))")
ffmpeg -y -v error </dev/null -i assembling/closing-slide.mp4 -i vo/h-closing.mp3 \
  -filter_complex "[1:a]apad=pad_dur=0.2[a]" -map 0:v -map "[a]" -t "$target" \
  -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p -c:a aac -b:a 128k assembling/closing-vo.mp4
echo "file 'assembling/closing-vo.mp4'" >> concat.txt

ffmpeg -y -v error -f concat -safe 0 -i concat.txt -c copy goodbye-group-gouging-humanized.mp4
echo "DONE → goodbye-group-gouging-humanized.mp4"