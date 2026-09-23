#!/usr/bin/env bash
# Build the narrated master: for each clip, freeze the LAST frame (tpad clone) for
# the VO's tail so the visual holds while narration finishes, then mux the VO, concat.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p assembled

# order: video-clip | vo | extra-tail-seconds-after-natural-end
# tpad only ADD tail; the natural clip plays, then a frozen tail extends it.
# For clips shorter than the VO, pad = vo_len - clip_len (+ small gap).
# We pad generously then trim to vo duration.
targets="title-clip.mp4:vo/vo-title.mp3:0.00
cost-model-divergence.mp4:vo/vo-divergence.mp3:0.00
cost-model-wall.mp4:vo/vo-wall.mp3:0.00
cost-model-three-ways.mp4:vo/vo-three.mp3:0.00
cost-model-per-participant.mp4:vo/vo-participant.mp3:0.00
cost-model-redundancy.mp4:vo/vo-redundancy.mp3:0.00
cost-model-crossover.mp4:vo/vo-crossover.mp3:0.00
value-flow-diagram.mp4:vo/vo-value.mp3:0.00
fear-loop-diagram.mp4:vo/vo-fear.mp3:0.00"

: > concat.txt
while IFS=: read -r clip vo _; do
  vo_len=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$vo")
  clip_len=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$clip")
  total=$(python3 -c "print('%.2f' % (float('${vo_len}') + 0.3))")
  # freeze last frame until audio is done; add a little air
  out="assembled/$(basename "$clip")"
  echo "  $clip (${clip_len}s) ← $vo (${vo_len}s) → ${total}s"
  # tpad holds the final frame; then trim the whole thing to the vo length (+0.3 air)
  ffmpeg -y -v error </dev/null \
    -i "$clip" -i "$vo" \
    -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=${vo_len}[v];[1:a]apad=pad_dur=0.3[a]" \
    -map "[v]" -map "[a]" \
    -t "$total" \
    -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p -c:a aac -b:a 128k \
    "$out"
  echo "file '$out'" >> concat.txt
done <<< "$targets"

ffmpeg -y -v error -f concat -safe 0 -i concat.txt -c copy goodbye-group-gouging-with-vo.mp4
echo "DONE → goodbye-group-gouging-with-vo.mp4"