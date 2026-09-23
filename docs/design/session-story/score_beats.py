#!/usr/bin/env python3
"""score_beats.py — run OpenJ over the storyboard beats (scene signif + act).

Loads storyboard.json, builds one record PER BEAT for (1) a noul "is this a
story beat?" and (2) a choice "which act?", batches all through score_cached,
and writes storyboard_scored.json with per-beat confidence + act from Jev.
"""
import json, sys, time
from pathlib import Path
from math import exp

import torch
sys.path.insert(0, "/tmp/Open-Jev")
from jev.model import DecisionModel

CHECKPOINT = Path("/home/service/.cache/huggingface/hub/models--ZefanCai--Open-Jev-2B/snapshots/0c7aa498b1627be8da4acf34c863ff0ee0a92785/package/checkpoint")
IN = Path("/home/service/development/irl-coop-stack-v2/docs/design/session-story/storyboard.json")
OUT = Path("/home/service/development/irl-coop-stack-v2/docs/design/session-story/storyboard.json")

def softmax(values, temperature=1.0):
    z = [exp(v / temperature) for v in values]
    s = sum(z)
    return [w / s for w in z]

def build_records(beats):
    recs = []
    for i, b in enumerate(beats):
        st = {"title": b["title"], "date": b["date"],
              "magnitude": b["magnitude"], "messages": b["messages"]}
        recs.append({
            "id": f"in_{i}", "state": st, "kind": "noul",
            "question": "Does this session beat belong in the story of this period of work? "
                        "Signal sessions change state; chatter and trivial tests do not.",
            "options": ["no", "yes"], "answer_keys": ["false", "true"]})
        recs.append({
            "id": f"act_{i}", "state": st, "kind": "choice",
            "question": "Which act of a three-act story does this beat belong to?",
            "options": ["Act I: setup", "Act II: central tension", "Act III: resolution"],
            "answer_keys": ["act_I", "act_II", "act_III"]})
    return recs

def main():
    story = json.loads(IN.read_text())
    beats = story["beats"]
    recs = build_records(beats)
    t0 = time.time()
    model = DecisionModel.load(CHECKPOINT, device="cpu")
    print("load_seconds=%.1f" % (time.time() - t0), flush=True)
    temp = json.loads((Path(CHECKPOINT) / "temperature.json").read_text())["temperature"]
    t1 = time.time()
    logits, cache = model.score_cached(recs, batch_size=32)
    print("n_records=%d infer_seconds=%.1f" % (len(recs), time.time() - t1), flush=True)
    probs = [softmax(row.float().cpu().tolist(), temperature=temp) for row in logits]

    for i, b in enumerate(beats):
        p_in = probs[2 * i][1]          # noul: yes = answer_keys index 1
        act_probs = probs[2 * i + 1]    # choice acts
        act = ["I", "II", "III"][int(max(range(3), key=lambda k: act_probs[k]))]
        b["confidence"] = round(p_in, 3)      # probability storybeat
        b["act"] = f"Act {act}"
        b["act_conf"] = round(act_probs[(0 if act=="I" else 1 if act=="II" else 2)], 3)
        b["_source"] = "Open-Jev-2B"
        b["story"] = p_in >= 0.55

    # sort kept-first, then by date
    story["beats"] = beats
    story["story"] = "Storyboard scored by Open-Jev (noul scene-sign-in + act placement)."
    OUT.write_text(json.dumps(story, indent=2, ensure_ascii=False))
    print("wrote", OUT)
    kept = sum(1 for b in beats if b["story"])
    print(f"kept beats: {kept}/{len(beats)}")
    for b in beats:
        tag = "KEEP" if b["story"] else "drop"
        print(f"  {tag:4} {b['act']:7} conf={b['confidence']:.2f} {b['magnitude']:>12,} | {b['title'][:44]}")

if __name__ == "__main__":
    main()