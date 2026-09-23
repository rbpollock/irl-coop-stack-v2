#!/usr/bin/env python3
"""D6 bench — paired (strong vs cheap) commit-title draft on REAL commit subjects.

Calls DeepSeek (key read from ~/.hermes/.env at runtime, never printed), scores
each model's title with a rule+overlap proxy, and prints M3 quality parity.

Usage:  python3 d6_bench.py [--n 10] [--dry]
"""
from __future__ import annotations

import json, os, re, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

ENV = Path(os.path.expanduser("~/.hermes/.env"))
BASE = "https://api.telnyx.com/v2/ai/chat/completions"  # OpenAI-compatible via Telnyx
STRONG, CHEAP = "deepseek-ai/DeepSeek-V4-Flash-0731", "deepseek-ai/DeepSeek-V4.1-Flash"


def _key() -> str:
    keyvar = "TELNYX_API_KEY"
    if os.environ.get(keyvar):
        return os.environ[keyvar]
    for line in ENV.read_text(errors="ignore").splitlines():
        if line.startswith(keyvar + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no TELNYX_API_KEY")


def call(model: str, prompt: str, key: str) -> str:
    body = {
        "model": model, "temperature": 0.0, "max_tokens": 60,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        BASE, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    return (d["choices"][0]["message"]["content"] or "").strip()


def subjects(repo: str, n: int = 12) -> list[str]:
    out = subprocess.run(["git", "-C", repo, "log", "--format=%s", f"-{n * 3}"],
                         capture_output=True, text=True).stdout.splitlines()
    seen = []
    for s in out:
        s = s.strip()
        if s and s not in seen:
            seen.append(s)
    return seen[:n]


def overlay(a: str, ref: str) -> float:
    a = a.lower()
    ref = ref.lower()
    if not ref:
        return 0.0
    tokens = re.findall(r"[a-z0-9-]{3,}", ref)
    if not tokens:
        return 0.0
    hit = sum(1 for t in tokens if t in a)
    return hit / len(tokens)


def score(output: str, ref: str) -> float:
    if not output or len(output) > 80:
        return 0.0
    o = overlay(output, ref)
    return min(1.0, max(o, 0.1 if len(output) >= 12 else 0.0))


def main() -> int:
    dry = "--dry" in sys.argv
    n = 10
    for a in sys.argv[1:]:
        if a.isdigit():
            n = int(a)
    tasks = subjects("/home/service/development/irl-coop-stack-v2", n)
    if not tasks:
        print("no commit subjects"); return 1
    key = None if dry else _key()
    inc, cheap = [], []
    for ref in tasks:
        prompt = (f"A developer changed a repo. Write a one-line commit message "
                  f"(max 72 chars) for the change described. Change: {ref}")
        if dry:
            inc.append(score(ref, ref)); cheap.append(score(ref, ref)); continue
        try:
            s_inc = score(call(STRONG, prompt, key), ref)
            s_chp = score(call(CHEAP, prompt, key), ref)
        except urllib.error.HTTPError as e:
            print("skip", ref[:40], "HTTP", e.code, e.read().decode()[:160])
            continue
        except Exception as e:
            print("skip", ref[:40], "err", type(e).__name__, str(e)[:120])
            continue
        inc.append(s_inc); cheap.append(s_chp)
    print(f"D6 bench: {len(tasks)} tasks, DRY={dry}")
    print(f"  incumbent {STRONG} proxy: {sum(inc)/max(1,len(inc)):.2f}  accept>=0.5: {sum(1 for x in inc if x>=.5)}")
    print(f"  cheap     {CHEAP}  proxy: {sum(cheap)/max(1,len(cheap)):.2f}  accept>=0.5: {sum(1 for x in cheap if x>=.5)}")
    return 0


if __name__ == "__main__":
    main()