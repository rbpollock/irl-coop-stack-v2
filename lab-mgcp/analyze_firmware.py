#!/usr/bin/env python3
"""
Analyze a ShoreTel IP phone firmware binary (sevapp.bin / bootROM) for MGCP
protocol intelligence.

Extracts printable strings and categorizes them to surface the registration /
hook-state / display handshake the phone expects. Run:
    python3 analyze_firmware.py /path/to/sevapp.bin
"""
import re
import sys
from collections import defaultdict

MINLEN = 4

# Categorization keywords (lowercase).
GROUPS = {
    "MGCP verbs": ["rsip", "auep", "crcx", "mdcx", "dlcx", "rqnt", "ntfy", "epcf"],
    "MGCP params/headers": ["x-shoredisplay", "x-shoremodel", "x-shore", "remoteconnectiondescriptor",
                            "localconnectiondescriptor", "requestedevent", "signalevent",
                            "observedevents", "notifiedentity", "callid", "connectionid",
                            "requestidentifier", "responseack", "restartmethod", "restartdelay"],
    "error/state strings": ["on hook", "off hook", "on-hook", "off-hook", "no service",
                            "requesting service", "requesting", "in service", "already on",
                            "forbidden", "protocol error", "bad header", "unrecognized",
                            "disconnected", "restart", "keepalive"],
    "signals/events": ["l/dl", "l/hd", "l/hu", "l/hf", "l/ro", "l/rg", "l/cw", "l/ci",
                       "ky/ls", "ky/ks", "ky/fk", "d/0", "d/1", "d/2", "d/3", "d/4", "d/5",
                       "d/6", "d/7", "d/8", "d/9", "d/*", "d/#", "bp/hd", "bp/hu", "bp/beep"],
    "config/firmware files": ["shore_sevg", "shore_sev", "sevgcustom", "sevcustom", "sevapp",
                              "bootrom", "boot_rom", "country_", "language_", "shore_",
                              ".txt", ".bin", "MgcServers", "sntpserver", "5004Enable",
                              "RtcpEnable", "ftpservers", "option 156"],
    "SDP/media": ["PCMU", "PCMA", "G729", "G722", "RTP", "SDP", "m=audio", "a=rtpmap",
                  "ptime", "5004", "sendrecv", "sendonly", "recvonly", "inactive"],
    "display text": ["ext ", "extension", "john", "newcall", "history", "options", "ready",
                     "dialing", "call ", "held", "ringing", "connected", "idle"],
    "protocol strings": ["mgcp 1.0", "mgcp", "200 ", "250 ", "400 ", "401 ", "402 ", "500 ",
                         "501 ", "510 ", "511 ", "512 ", "515 ", "518 ", "520 ", "521 ", "522 ",
                         "526 ", "527 ", "538 ", "s:", "r:", "i:", "c:", "x:", "f:", "m:", "l:",
                         "rm:", "x-shore"],
}


def strings_from(data):
    """Yield printable ASCII runs of >= MINLEN chars."""
    run = []
    for b in data:
        if 32 <= b < 127:
            run.append(chr(b))
        else:
            if len(run) >= MINLEN:
                yield "".join(run)
            run = []
    if len(run) >= MINLEN:
        yield "".join(run)


def main(path):
    with open(path, "rb") as f:
        data = f.read()
    print(f"=== {path}: {len(data)} bytes ===\n")

    strs = list(strings_from(data))
    print(f"total printable strings (>= {MINLEN} chars): {len(strs)}\n")

    hits = defaultdict(list)
    for s in strs:
        low = s.lower()
        for group, kws in GROUPS.items():
            if any(k in low for k in kws):
                hits[group].append(s)
                break

    for group, arr in hits.items():
        # dedupe preserving order
        seen, uniq = set(), []
        for s in arr:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        print(f"--- {group} ({len(uniq)}) ---")
        for s in uniq[:80]:
            print("  " + s)
        print()

    # Also dump any MGCP-looking verb lines and 3-digit responses explicitly.
    print("--- MGCP verb lines / responses (explicit) ---")
    pat = re.compile(r"^(RSIP|AUEP|CRCX|MDCX|DLCX|RQNT|NTFY|EPCF|\d{3})\b", re.I)
    for s in strs:
        if pat.match(s):
            print("  " + s)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python3 analyze_firmware.py <firmware.bin>")
        sys.exit(1)
    main(sys.argv[1])
