#!/usr/bin/env python3
"""Three-stage clean pipeline — SAME absolute timeline for audio & video.

The fix over the previous version: audio VOs and video slides are BOTH placed on
a single shared absolute timeline (seconds from t=0). No reliance on `-shortest`.

  Stage 1 VIDEO: one silent track. Slide k occupies [slide[k], slide[k]+win_k].
    slide[k] = vo_start[k] + LEAD for lead slides, else vo_start[k]. Each slide
    holds its last frame (tpad) for exactly its window.
  Stage 2 AUDIO: one track. Each VO is placed at its absolute vo_start[k]
    (silence up to it), then its duration. VO k ends where VO k+1 begins →
    never, ever overlaps.
  Stage 3 STITCH: mux. Both tracks end at the SAME total length, so nothing is
    truncated and slide/audio align exactly.
"""
import os, subprocess, sys

VIDEO = os.path.abspath(os.path.join(os.path.dirname(__file__), "video"))
SEG = "/tmp/irl-video-build"
OUT = os.path.join(VIDEO, "goodbye-group-gouging-fast.mp4")

LEAD = 1.2
LEAD_SLIDES = {1, 6, 9}   # divergence, crossover, closing

NARR = [
    ("h-title","title-clip.mp4"), ("h-divergence","cost-model-divergence.mp4"),
    ("h-wall","cost-model-wall.mp4"), ("h-three","cost-model-three-ways.mp4"),
    ("h-participant","cost-model-per-participant.mp4"), ("h-redundancy","cost-model-redundancy.mp4"),
    ("h-crossover","cost-model-crossover.mp4"), ("h-value","value-flow-diagram.mp4"),
    ("h-fear","fear-cluster-diagram.mp4"), ("h-closing","CLOSING"),
]

def dur(p):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                        "-of","default=noprint_wrappers=1:nokey=1",p],capture_output=True,text=True)
    return float(r.stdout.strip())

os.makedirs(SEG, exist_ok=True)
for x in os.listdir(SEG):
    os.remove(os.path.join(SEG, x))

VO = [f"{VIDEO}/vo/{n}.mp3" for n, _ in NARR]
vo_len = [dur(v) for v in VO]

# ---- SHARED ABSOLUTE TIMELINE
# Audio: non-overlapping, VO k ends where VO k+1 begins.
vs = [0.0]
for k in range(1, len(NARR)):
    vs.append(vs[k-1] + vo_len[k-1])
# Slide k appears at vs[k] (+LEAD if lead)
slide = [vs[k] + (LEAD if k in LEAD_SLIDES else 0) for k in range(len(NARR))]
# Total length: the closing must extend far enough to hold its VO fully no matter lead.
# Choose total = full audio end; and ensure the last slide shows until audio end +0.6.
audio_end = vs[-1] + vo_len[-1]
TOTAL = audio_end + 0.6

# ---- STAGE 1: VIDEO track (silent) = concat of per-slide held clips
vid_clips = []
for k, (n, clip) in enumerate(NARR):
    start = slide[k]
    end = slide[k+1] if k+1 < len(NARR) else TOTAL
    win = max(end - start, vo_len[k])   # at least cover its own VO fully
    if clip == "CLOSING":
        dur_c = max(win, vo_len[k] + 0.4)
        cp = f"{SEG}/closing.mp4"
        subprocess.run(["ffmpeg","-y","-v","error","-loop","1","-i",f"{VIDEO}/closing-slide.png",
            "-vf","scale=1920:1080,format=yuv420p","-t",f"{dur_c}","-r","24",
            "-c:v","libx264","-preset","fast","-crf","22",cp], check=True)
        vp = cp
    else:
        vp = f"{VIDEO}/{clip}"
    out = f"{SEG}/vid{k}.mp4"
    subprocess.run(["ffmpeg","-y","-v","error","-i",vp,
        "-vf",f"tpad=stop_mode=clone:stop_duration={win},setsar=1,format=yuv420p",
        "-t",f"{win}","-c:v","libx264","-preset","fast","-crf","22","-an",out], check=True)
    vid_clips.append((out, win))

with open(f"{SEG}/v.txt","w") as f:
    for o, _ in vid_clips: f.write(f"file '{o}'\n")
subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",f"{SEG}/v.txt","-c","copy",f"{SEG}/video.mp4"], check=True)

# ---- STAGE 2: AUDIO track, absolute placement (silence -> VO at vs[k])
def silence(d, out):
    d = max(0.001, d)
    subprocess.run(["ffmpeg","-y","-v","error","-f","lavfi","-i","anullsrc=r=24000:cl=mono",
        "-t",f"{d}","-c:a","aac","-b:a","160k",out], check=True)

pieces = []
cur = 0.0
for k, path in enumerate(VO):
    need = vs[k] - cur
    if need > 0.03:
        gp = f"{SEG}/gap{k}.m4a"; silence(need, gp); pieces.append(gp)
    vp = f"{SEG}/vo{k}.m4a"
    subprocess.run(["ffmpeg","-y","-v","error","-i",path,"-c:a","aac","-b:a","160k",vp], check=True)
    pieces.append(vp)
    cur = vs[k] + vo_len[k]
# pad the tail to TOTAL so audio covers the full window
need = TOTAL - cur
if need > 0.03:
    tl = f"{SEG}/taill.m4a"; silence(need, tl); pieces.append(tl)

with open(f"{SEG}/a.txt","w") as f:
    for p in pieces: f.write(f"file '{p}'\n")
subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",f"{SEG}/a.txt","-c","copy",f"{SEG}/audio.m4a"], check=True)

# ---- STAGE 3: STITCH (no -shortest; both tracks now same/app close length)
subprocess.run(["ffmpeg","-y","-v","error","-i",f"{SEG}/video.mp4","-i",f"{SEG}/audio.m4a",
    "-map","0:v","-map","1:a","-c:v","copy","-c:a","copy",
    "-t",f"{TOTAL}",OUT], check=True)
print("audio_end=",round(audio_end,1),"TOTAL=",round(TOTAL,1))
print("vs:",[round(x,1) for x in vs])
print("slide:",[round(x,1) for x in slide])
print("DONE →",OUT)