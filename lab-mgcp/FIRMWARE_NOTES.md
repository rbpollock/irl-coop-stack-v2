# FIRMWARE_NOTES.md — ShoreTel IP 230g (SEVG) firmware reverse-engineering

Status: **firmware obtained, decoded, strings extracted; exact function decompilation pending.**

## What we have

| File | Size | What it is |
|---|---|---|
| `firmware/shore_sevgap.ebin` | 1,951,838 | 230g **app** firmware (ShoreTel container) |
| `firmware/shore_sevgbb.ebin` | 1,636,681 | 230g **bootROM** (ShoreTel container) |
| `firmware/appmgcp_decompressed.bin` | 5,594,816 | the app, gzip-decompressed (the real VxWorks image) |
| `firmware/sevgap_strings.txt` | ~42k strings | full `strings -a -n 5` dump of the app |

The `.ebin` files came from the **ShoreTel 14.2 build** (`19.49.8600.0`), from
`customers.btxchange.com/Downloads/ShoreTel/ShoreTel_14.2_Build_19.49.8600.0/`.
They live in `Data11.cab`, which is the second volume of a **multi-volume .cab**
(`Data1.cab` + `Data11.cab` — 7z reports "Can't open volume: Data11.cab" until
both are present and named correctly).

## The container format (`.ebin`)

- **Header** (first ~0x100 bytes): magic `bc 09 00 28 …`, then the internal name
  `ap_SEVG_mg` (at `0x1a`), a load address `0x00400080`, and metadata.
- **Payload**: a **gzip stream starting at offset `0x100`**.

Decode (Python):
```python
import zlib
data = open("shore_sevgap.ebin","rb").read()
out  = zlib.decompress(data[0x100:], 16 + zlib.MAX_WBITS)   # -> 5.6 MB
```

## The app image

- **Architecture**: MIPS, big-endian, 32-bit. **Broadcom BCM1103** SoC
  (`bcm1103*` driver strings everywhere).
- **OS**: VxWorks (taskSpawn/semLib/taskHook symbols; `stts_module.o` / `stts_zin`
  in the ShoreGear boot scripts — "stts" = ShoreTel Telephony Switch).
- **Load base**: `0x00400000` (header entry `0x00400080`; `$gp` initialized to
  `0x80561eb0` via `lui`+`addiu`).
- **Internal app name**: `appmgcp.bin` (referenced in the image as `app1/appmgcp.ebin`).
- A **VxWorks symbol table is present** (~350 `_func` names near `0x406490` onward)
  but its entry layout hasn't been parsed yet — that's the key to naming functions.

## Key strings (authoritative protocol facts)

### The `402` bug, root-caused
- `402` → **`Phone already on hook`** (`0x45e4d4` file / `0x85e4d4` load)
- `401` → `Phone already off hook`
- `510` → `Bad header`
- The phone's *hook state* is what's being rejected — not protocol syntax.

### Periodic RSIP (the ~240s "RM: disconnected" loop)
- `Disconnected timer elapsed, sending first RSIP @ tick - %ld (%ld mS)`
- `RESTART TIMER ELAPSED! Sending first RSIP @ tick - %ld (%ld mS)`
- The phone drops into a **"disconnected"** state on a timer and re-RSIPs.

### Connection state machine
- `Command received in 'disconnected' state, short-circuiting disconnected timer...`
- `Command received in 'restart' state, short-circuiting restart timer...`
- `Restart continuing in disconnected state...`
- `Event during restart or disconnect. NTFY should be piggybacked!`
- So: any command short-circuits the timer (phone → "connected"), **but the hook
  state does not follow** — that's the re-pickup `402` after a disconnect cycle.

### "No Service" / "Requesting Service" state
- `ccIsNoService`, `ccInitEndpt_noService`, `ccIsConnected`, `ccPhoneIsIdle`
- `ccEptDisconnected`
- `ccProvision`, `ccProvisionValue` (provisioning from DHCP option 156 + Flash;
  `ccProvisionValue` fields `Max2`, `Mode`, `RtoInit`, `ToMin`, `TsMax` = MGCP
  retransmission params)
- `Endpoint is not ready`, `Endpoint is restarting`

### MGCP command handlers (function names — anchors for decompilation)
- `mgProcessRQNT`, `mgProcessRQNTSignals`, `mgProcessAUEP`, `SendNTFYCommand`,
  `ParseEmbedRQNT`, `updateOfferAnswerStateDLCX`, `mgcpReadThread`,
  `ccMgcpStartup`, `ccMgcpIsConfigured`, `mgcpWaveRingEvent`
- Message templates: `RSIP %u %s@%s %s`, `NTFY %u %s@%s %s`
- Validation rules: `ConnectionId(I:) is forbidden in CRCX`,
  `ConnectionMode(M:) forbidden for DLCX`, `LocalConnectionOptions(L:) forbidden
  for DLCX`, wildcard rules (`'all of' wildcard forbidden for CRCX`, etc.)

### Display / hook switch
- `ccDisplayLine1=%s`, `ccDisplayLine2=%s`, `ccDisplayString=%s`, `ccDisplayTitle`
- `HS OFF hook` / `HS ON hook` (hook switch)
- `ccPlayDtone: unrecognized signal %d`

### Config keys (`TLV_*` NVRAM)
- `TLV_MGCP_CACHED_MGCIP`, `TLV_MGCP_MGCIP`, `TLV_MGCP_EPID_STYLE`,
  `TLV_MGCP_LOGFLAG`, `TLV_MGCP_LOGPORT`, `TLV_MGCP_LOGIP`, `MgcpBackoffEnable`,
  `MgcpVpnMaxRetx`, `mgcp.cfg`

## The working hypothesis

"No Service" (`ccIsNoService` true) → the phone treats itself as **"disconnected"**
(timer-driven RSIP) → the hook state never latches → **`402 Phone already on hook`**
on re-pickup. Clearing "No Service" via **provisioning** (complete DHCP option 156
`ftpservers=…,country=n,language=n,…` + the full config set + the right
registration exchange) should fix *both* the "Requesting Service" LCD *and* the
re-pickup dial tone in one stroke.

## Next steps (unfinished)

1. **Load the VxWorks symbol table** so `ccIsNoService` / `mgProcessRQNT` get
   their real addresses — parse the entries before `0x406490` (the entry layout
   isn't yet known; try 12/16/20-byte structs with `name_offset → value`).
2. **Trace the string references** — the MIPS Constant Reference Analyzer found
   *no* `lui`+`addiu` to the strings, so they're referenced via a
   format-string/pointer table or `$gp`-relative access; find the indirection.
3. **Decompile `ccIsNoService`** to get the exact "No Service → in service"
   condition, then make `mod_mgcp` satisfy it.

## Tooling (reproducible)

- Ghidra 12.1.3 (`/tmp/ghidra/ghidra_12.1.3_PUBLIC/`), OpenJDK 21
  (`/usr/lib/jvm/java-21-openjdk-amd64`), PyGhidra for headless scripts.
- Headless run (note: `.java` scripts fail on OSGi; use PyGhidra `.py` via
  `pyghidra_launcher.py -H`; `setImageBase` is NOT a PyGhidra global — use
  `currentProgram.setImageBase(currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(0x400000), True)`):
  ```
  yes | python3 <ghidra>/Ghidra/Features/PyGhidra/support/pyghidra_launcher.py -H <ghidra> \
    /tmp/ghidra_proj proj1 -import appmgcp_decompressed.bin \
    -processor "MIPS:BE:32:default" -loader BinaryLoader -overwrite \
    -preScript SetBase.py -analysisTimeoutPerFile 180 \
    -scriptPath /tmp -postScript DumpMgcp.py
  ```
- `analyze_firmware.py` in this dir does a fast `strings`-categorization pass
  (no Ghidra needed) — good first look at any new `.bin`.

## FTP provisioning file set (for the live phone)

`ftp_data/` should contain (the 230g model is **SEVG**, not SEV):
- `shore_sevg.txt` — base config (`DHCP 1`, `Include "Country_$Country.txt"`,
  `Include "Language_$Language.txt"`, `RtcpEnable …`, `5004Enable 1`, `MgcServers
  <ip>`, `sntpserver <ip>`)
- `sevgcustom.txt` — custom overrides (NOT `sevcustom.txt`)
- `shore_<MAC>.txt` — device config (lowercase MAC)
- `Country_*.txt`, `Language_*.txt` — localization (the `Include` targets)
- `shore_sevgap.ebin` + `shore_sevgbb.ebin` — the firmware (only fetched if the
  phone's flashed version mismatches)
