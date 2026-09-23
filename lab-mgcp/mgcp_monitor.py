#!/usr/bin/env python3
"""
Live MGCP monitor for the ShoreTel IP 230 lab.

Tails the FreeSWITCH log FILE (not the buffered console), parses MGCP traffic
into structured events, keeps a rolling history, and serves a browser dashboard
that polls /snapshot. Stdlib only.

Run:  python3 mgcp_monitor.py          (serves http://<host>:8099)
"""
import json
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONTAINER = "lab-mgcp-freeswitch-1"
PORT = 8099

HDR_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+).*?mgcp_protocol\.c:\d+ "
    r"(RX from|TX to) ([\d.]+:\d+)"
)
EVENT_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+).*?mgcp_protocol\.c:\d+ "
    r"Phone \S+ (went OFF-HOOK \(hd\)|went ON-HOOK \(hu\)|"
    r"connection established \(I: (\S+)\)|pressed digit: (\S+))"
)
RESP_RE = re.compile(r"^(\d{3})\s+(.*)$")

history = []          # list of dict events (most recent last), capped
history_lock = threading.Lock()
MAX_HISTORY = 500


def push(ev):
    with history_lock:
        history.append(ev)
        if len(history) > MAX_HISTORY:
            del history[: len(history) - MAX_HISTORY]


def classify_first_line(line):
    m = RESP_RE.match(line)
    if m:
        code = int(m.group(1))
        return ("response", None, code, code >= 400, m.group(2))
    verb = line.split(" ", 1)[0] if line else ""
    return ("request", verb, None, False, "")


def monitor_loop():
    while True:
        try:
            proc = subprocess.Popen(
                ["docker", "exec", CONTAINER, "tail", "-n", "200", "-f",
                 "/usr/local/freeswitch/log/freeswitch.log"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                bufsize=1,
            )
        except Exception as e:
            push({"type": "sys", "msg": f"tail failed: {e}"})
            time.sleep(3)
            continue

        state = "scan"
        hdr = None
        buf = []
        try:
            for raw in proc.stdout:
                if raw is None:
                    break
                line = raw.rstrip("\n")
                if state == "scan":
                    m = HDR_RE.match(line)
                    if m:
                        hdr = {"ts": m.group(1), "dir": m.group(2), "addr": m.group(3)}
                        state = "expect_sep"
                        continue
                    m = EVENT_RE.match(line)
                    if m:
                        ts = m.group(1)
                        if "OFF-HOOK" in m.group(2):
                            push({"type": "state", "ts": ts, "kind": "offhook"})
                        elif "ON-HOOK" in m.group(2):
                            push({"type": "state", "ts": ts, "kind": "onhook"})
                        elif m.group(2).startswith("connection"):
                            push({"type": "state", "ts": ts, "kind": "conn",
                                  "connid": m.group(3)})
                        else:
                            push({"type": "state", "ts": ts, "kind": "digit",
                                  "digit": m.group(4)})
                        continue
                elif state == "expect_sep":
                    if line == "---":
                        state = "in_body"
                        buf = []
                    continue
                elif state == "in_body":
                    if line == "---":
                        if buf and hdr:
                            kind, verb, code, is_error, desc = classify_first_line(buf[0])
                            push({"type": "msg", "ts": hdr["ts"],
                                  "dir": hdr["dir"], "addr": hdr["addr"],
                                  "kind": kind, "verb": verb, "code": code,
                                  "is_error": is_error, "desc": desc,
                                  "first": buf[0], "body": buf})
                        state = "scan"
                        hdr = None
                        buf = []
                    else:
                        buf.append(line)
        except Exception as e:
            push({"type": "sys", "msg": f"monitor error: {e}"})
        try:
            proc.terminate()
        except Exception:
            pass
        push({"type": "sys", "msg": "log stream ended — reconnecting…"})
        time.sleep(2)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/snapshot"):
            self._snapshot()
        elif self.path == "/":
            self._html()
        else:
            self.send_response(404)
            self.end_headers()

    def _snapshot(self):
        since = 0
        if "?" in self.path:
            for kv in self.path.split("?", 1)[1].split("&"):
                if kv.startswith("since="):
                    try:
                        since = int(kv.split("=", 1)[1])
                    except ValueError:
                        pass
        with history_lock:
            events = history[since:]
            nxt = len(history)
        body = json.dumps({"events": events, "next": nxt})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode())

    def _html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode())

    def log_message(self, format, *args):
        pass


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MGCP monitor — ShoreTel IP 230</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace;
         background: transparent; color: var(--foreground,#e6e6e6); margin: 0; }
  header { display:flex; gap:12px; align-items:center; flex-wrap:wrap;
           padding:10px 12px; border-bottom:1px solid var(--border,#333); }
  header h1 { font-size:14px; margin:0; font-weight:600; }
  .pill { border:1px solid var(--border,#444); border-radius:6px;
          padding:3px 9px; font-size:12px; }
  .pill b { color: var(--accent,#7cc); }
  .controls { display:flex; gap:8px; margin-left:auto; flex-wrap:wrap; }
  .controls label { font-size:12px; display:flex; gap:4px; align-items:center;
                    color: var(--muted-foreground,#999); }
  #status { color: var(--muted-foreground,#888); font-size:11px; padding:0 12px; }
  #log { overflow-y:auto; max-height: calc(100vh - 84px); padding:8px 12px; }
  .row { display:flex; gap:10px; padding:3px 0; border-bottom:1px solid
         rgba(128,128,128,.08); }
  .ts { color: var(--muted-foreground,#888); white-space:nowrap; }
  .dir { width:34px; text-align:center; font-weight:700; border-radius:4px; }
  .dir.RX { color:#4ade80; } .dir.TX { color:#60a5fa; }
  .first { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1; }
  .err .first { color:#f87171; }
  .code { font-weight:700; width:34px; text-align:center; }
  .code.ok { color:#4ade80; } .code.bad { color:#f87171; }
  .state { color:#fbbf24; font-weight:600; }
  .sys { color:#94a3b8; font-style:italic; }
  details summary { cursor:pointer; color:var(--muted-foreground,#888); }
  details pre { white-space:pre-wrap; color:var(--muted-foreground,#999);
                margin:2px 0 6px 44px; }
</style>
</head>
<body>
<header>
  <h1>MGCP monitor</h1>
  <span class="pill">hook: <b id="st-hook">—</b></span>
  <span class="pill">conn: <b id="st-conn">—</b></span>
  <span class="pill">last error: <b id="st-err">—</b></span>
  <div class="controls">
    <label><input type="checkbox" id="f-rx" checked> RX</label>
    <label><input type="checkbox" id="f-tx" checked> TX</label>
    <label><input type="checkbox" id="f-state" checked> state</label>
    <label><input type="checkbox" id="f-err"> errors only</label>
    <label><input type="checkbox" id="f-pause"> pause</label>
    <button id="clear">clear</button>
  </div>
</header>
<div id="status">connecting…</div>
<div id="log"></div>
<script>
const log = document.getElementById('log');
const $ = (id) => document.getElementById(id);
const els = {hook:$('st-hook'), conn:$('st-conn'), err:$('st-err')};
let paused = false, autoScroll = true, next = 0;

log.addEventListener('scroll', () => {
  autoScroll = log.scrollTop + log.clientHeight >= log.scrollHeight - 40;
});

function esc(s) { return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function render(ev) {
  if (ev.type === 'msg') {
    const show = (ev.dir === 'RX' ? $('f-rx').checked : $('f-tx').checked);
    if (!show) return;
    if ($('f-err').checked && !ev.is_error) return;
    const cls = ev.is_error ? ' err' : '';
    const code = ev.code != null
      ? `<span class="code ${ev.code>=400?'bad':'ok'}">${ev.code}</span>`
      : `<span class="code"></span>`;
    const body = ev.body && ev.body.length > 1
      ? `<details><summary>▾</summary><pre>${esc(ev.body.join('\n'))}</pre></details>` : '';
    log.insertAdjacentHTML('beforeend',
      `<div class="row${cls}"><span class="ts">${esc(ev.ts.slice(11))}</span>` +
      `<span class="dir ${ev.dir}">${ev.dir}</span>${code}` +
      `<span class="first">${esc(ev.first)}</span>${body}</div>`);
  } else if (ev.type === 'state') {
    if (!$('f-state').checked) return;
    let label;
    if (ev.kind === 'offhook') { label = '▼ OFF-HOOK'; els.hook.textContent='OFF-HOOK'; }
    else if (ev.kind === 'onhook') { label = '▲ ON-HOOK'; els.hook.textContent='ON-HOOK'; }
    else if (ev.kind === 'conn') { label = '⚡ conn ' + ev.connid; els.conn.textContent=ev.connid; }
    else { label = 'DIGIT ' + ev.digit; }
    log.insertAdjacentHTML('beforeend',
      `<div class="row"><span class="ts">${esc(ev.ts.slice(11))}</span>` +
      `<span class="state">${esc(label)}</span></div>`);
  } else if (ev.type === 'sys') {
    log.insertAdjacentHTML('beforeend',
      `<div class="row"><span class="ts"></span><span class="sys">${esc(ev.msg)}</span></div>`);
  }
  if (ev.type === 'msg' && ev.is_error) els.err.textContent = ev.code + ' ' + ev.desc;
  while (log.children.length > 800) log.removeChild(log.firstChild);
  if (autoScroll) log.scrollTop = log.scrollHeight;
}

async function poll() {
  if (paused) return;
  try {
    const r = await fetch('http://localhost:8099/snapshot?since=' + next);
    const data = await r.json();
    for (const ev of data.events) render(ev);
    next = data.next;
    $('status').textContent = 'live · ' + next + ' events';
  } catch (e) {
    $('status').textContent = 'disconnected — retrying';
  }
}

$('clear').onclick = () => { log.innerHTML = ''; };
$('f-pause').onchange = (e) => { paused = e.target.checked; if (!paused) poll(); };
$('f-rx').onchange = $('f-tx').onchange = $('f-state').onchange = $('f-err').onchange =
  () => { log.innerHTML=''; next=0; poll(); };

poll();
setInterval(poll, 1000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"MGCP monitor on http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
