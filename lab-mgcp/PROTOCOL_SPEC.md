# PROTOCOL_SPEC.md — ShoreTel IP 230/230g (SEV/SEVG) MGCP protocol

Reconstructed from the decoded firmware (`shore_sevgap.ebin` → `appmgcp.bin`, a
5.6 MB VxWorks image; MIPS/BE, Broadcom BCM1103). String-backed facts are marked
**(confirmed)**; inferences needing disassembly are marked **(hypothesis)**.

---

## 1. Platform

| Item | Value |
|---|---|
| SoC | Broadcom BCM1103 (MIPS32, big-endian) |
| OS | VxWorks (taskSpawn, semLib, WDB debug agent) |
| Firmware | `appmgcp.bin` (the MGCP application; named `shore_sevgap.ebin` in the install cab) |
| Boot block | `shore_sevgbb.ebin` |
| Load base | `0x00400000` |
| Default boot line | `bcm(0,0) host:app1/appmgcp.ebin h=192.168.0.100 e=0.0.0.0:ffffff00 g=0.0.0.0 u=user tn=target f=0x0008` |

The model self-reports `X-ShoreModel: SEVG` (IP 230g). SEV (230) and SEVG (230g)
share the same MGCP app; the "g" is hardware (VPN), not protocol.

---

## 2. Boot & firmware chain **(confirmed)**

1. bootROM (`shore_sevgbb.ebin`) boots the SoC.
2. Phone reads its boot line (DHCP option 156 / Flash) for the FTP server + path.
3. Phone FETCHES the app over FTP: `RETR app1/appmgcp.ebin` (skip if the flashed
   version already matches). This is the `appmgcp.ebin` seen in the boot line.
4. Phone loads `appmgcp.bin` and starts the MGCP task (`ccMgcpStartup`).

> Our lab phone already runs the app (it speaks MGCP), so the fetch is only for
> upgrades. "Requesting Service" is NOT a firmware-fetch stall.

---

## 3. Provisioning **(confirmed)**

Sources, in the phone's own strings:
- `ERROR: provisioning from DHCP` / `ERROR: provisioning from Flash`
- `ccProvision`, `ccProvisionValue` — fields incl. `RtoInit`, `ToMin`, `TsMax`,
  `Mode`, `Max2` (MGCP retransmission/timer parameters).
- DHCP option 156 carries: `ftpservers`, `country`, `language`, `layer2tagging`,
  `vlanid`.

Call-agent (MGCP server) config keys:
- `Remote` — primary Call Agent (and `add_remote_ppp_option` for PPP/VPN).
- `Alternate` / `Alternates: ` — failover Call Agents
  (`add_alternate_to_configuration_option`, `add_option_to_alternate_list`).
- `ccMgcIpAddr` (current) / `ccCachedMgcIpAddr` (cached), `ccMgcpIsConfigured`,
  `ccSetMgcpConfigured`.
- Message format seen in the code: `Remote:Alternate:%s@%d`.

---

## 4. Config file format (`shore_sevg.txt`) **(confirmed keys)**

| Key | Meaning |
|---|---|
| `DHCP 1` | DHCP on; also `vlanid`, `layer2tag`, `redirVlanID`, `redirLayer2tag` |
| `Remote <ip>` | Primary Call Agent address |
| `Alternate <ip>` / `Alternates: <list>` | Failover Call Agents |
| `5004Enable 1` | RTP port 5004 |
| `sntpserver <ip>` | SNTP server (phone syncs time at boot) |
| `Country <n>` / `countryName` | Localization (`Include "Country_$Country.txt"`) |
| `Language <n>` | Localization (`Include "Language_$Language.txt"`) |
| codecs | `CODEC_PCMU`, `CODEC_PCMA`, `CODEC_G729A`, `CODEC_G722`, `CODEC_BV16/32`, `CODEC_LINEARNB/WB`, `CODEC_G711U/A_WB` |

FTP fetch set (all confirmed in logs): base `shore_sevg.txt` + per-device
`shore_<MAC>.txt` + `sevgcustom.txt` + firmware (`app1/appmgcp.ebin`).

---

## 5. MGCP message layer **(confirmed)**

Message templates from the binary:
- `RSIP %u %s@%s %s` — endpoint restart; also `RSIP %u %s/*@%s %s` (wildcard).
- `RM: %s` — restart method; values present: `restart`, `disconnected`
  (`graceful`/`forced` NOT present in the 230g app).
- `NTFY %u %s@%s %s` — notification.
- `Z: %s@%s` — the `Z:` header (MGCP 1.0 requested-events/connection id).
- `CA@[%s]` — call-agent address.
- `MGCP %s CNX: endpt %d, cnx %d` — connection handling.
- `MGCP SIGNAL: endpt %d, cnx %d, evt %d (%s) = %s` — signal dispatch.
- `MGCP Parser error %d %s`, `%s: drop MGCP packet %s:%d<%s>`.
- `Retransmit %lu, attempt %d: @ tick - %ld (%ld mS)` — retransmission/RTO.

Handlers: `mgProcessRQNT`, `mgProcessRQNTSignals`, `mgProcessAUEP`,
`SendNTFYCommand`, `ParseEmbedRQNT`, `updateOfferAnswerStateDLCX`.

Validation rules (phone-enforced):
- `'all of' wildcard forbidden for CRCX`
- `'any of' wildcard forbidden for DLCX`
- `'any of' wildcard not allowed for AUEP`
- `ConnectionId(I:) is forbidden in CRCX`
- `ConnectionMode(M:) forbidden for DLCX`
- `LocalConnectionOptions(L:) forbidden for DLCX`
- `Cannot use wildcarding and specify ConnectionId(I:) for DLCX`

---

## 6. State machine **(confirmed strings, exact logic pending)**

- Connection states: `connected`, `disconnected`, `restart`.
- `Disconnected timer elapsed, sending first RSIP @ tick` and
  `RESTART TIMER ELAPSED! Sending first RSIP` → periodic RSIP every ~240 s.
- `Command received in 'disconnected' state, short-circuiting disconnected timer...`
  and `...'restart' state, short-circuiting restart timer...`.
- `Restart continuing in disconnected state...`.
- `Endpoint is restarting`, `Endpoint is not ready`.

Call/endpoint state: `ccIsConnected`, `ccIsRinging`, `ccEptDisconnected`,
`ccPhoneIsIdle`, `ccEndpt[CCPHONE].ringing`, `bv32_ltsf_ringing`,
`btUserExitRinging`, `CALL_CONFERENCE`, `CALL_CONFERENCE_VPN`.

Hook switch: `HS OFF hook` / `HS ON hook`.

---

## 7. Response/error codes **(confirmed)**

| Code | String |
|---|---|
| 401 | `Phone already off hook` |
| 402 | `Phone already on hook` |
| 510 | `Bad header` |
| 511 | `Unrecognized protocol extension` (digit-map `D/...` rejected → use discrete `d/N`) |

Display writers: `ccDisplayLine1=%s`, `ccDisplayLine2=%s`, `ccDisplayString=%s`,
`ccDisplayTitle`. ShoreTel extensions: `X-ShoreDisplay`, `X-ShoreDisplay2`
(empty value ⇒ `510 Bad header`).

---

## 8. The "No Service" mystery **(hypothesis, needs disassembly)**

Confirmed functions: `ccIsNoService`, `ccInitEndpt_noService`. The phone holds
"No Service" (our LCD shows "Requesting Service") while `ccIsNoService` is true.

**Hypothesis (strong):** the phone is "No Service" until it (a) provisions a
Call Agent (`ccMgcpIsConfigured` true via DHCP 156 or Flash `Remote`), and
(b) completes registration + receives its line appearance
(`KY/ls(1,<ext>)` + `KY/ks(1,id)`), i.e. is "in service". While "No Service",
the phone treats itself as "disconnected" (timer RSIP) and does NOT latch
off-hook — which is exactly the `402 Phone already on hook` on re-pickup.

**This unifies both bugs:** clearing "No Service" should fix the LCD *and* the
re-pickup dial tone. The exact clear-condition is the one thing left to pin via
disassembly of `ccIsNoService`.

---

## 9. Remaining work

### VxWorks symbol table — RESOLVED (stripped, not parseable)

The name string table lives at file offset **0x404b80 → 0x43fe14** (~60 KB,
several thousand C function names — VxWorks kernel + network + BSP + the
ShoreTel app's own `_func_evtLog*`/`cc*`/`mg*` functions), in link order
(roughly reverse-alphabetical). The `SYMBOL` struct is 20 bytes:

    { SL_NODE nameHNode; char *name; SYM_VALUE value; SYM_REF symref;
      SYM_GROUP group; SYM_TYPE type; }   // name@+4, value@+8, group@+16, type@+18

**The entry array (name→address) is NOT in the image.** Exhaustive search for
20-byte entries (name→string table, value→function address, all file/physical/
kseg0 interpretations) finds only false positives scattered through the code —
no dense contiguous array anywhere. The firmware was built **without the
downloadable symbol table** (`INCLUDE_SYM_TBL` off); the names remain only for
the error logger / WDB agent. There is no name→address mapping to recover.

Consequently the exact `ccIsNoService` logic cannot be pulled straight from the
binary — the string-reference indirection is also non-trivial (the `402` string
`Phone already on hook` @0x85e4d4 has **zero** direct `lui`+`addiu` refs and
zero pointer-table entries; it's reached via a computed/$gp path Ghidra's
constant analyzer doesn't model).

### Path forward (practical, not RE)

Since the symbol table is stripped, stop chasing disassembly. Test the "No
Service → in service" clear-condition **empirically against the live phone**:
present a fully-provisioned Call Agent (`Remote`/`Alternate` + DHCP option 156)
and complete register → line-appearance (`KY/ls`+`KY/ks`) → then observe whether
the LCD leaves "Requesting Service". `mod_mgcp` already does most of this; the
likely missing piece is the *provisioned Call Agent* signaling, not the MGCP flow.

## 10. RTP media encryption — SRTP (confirmed)

The phone encrypts the RTP audio with **standard SRTP (RFC 3711)**, not a
proprietary scheme. From the firmware:

| Component | Detail |
|---|---|
| Cipher suites | `AES_CM_128_HMAC_SHA1_80`, `AES_CM_128_HMAC_SHA1_32`, `AES_CM_128_HMAC_SHA1_32_UNAUTHENTICATED`, plus AES-192/256 and `3DES(168)` |
| Key exchange | **SDES (RFC 4568)** — `a=crypto:%d %s inline:%s` (key inlined in the SDP body) |
| Engine | `SMAPI` ("Secure Media API"): `SMAPI_CreateContext/CreatePolicy`, `SMAPI_ProtectRTP`/`UnProtectRTP`, `SMAPI_ProtectRTCP`/`UnprotectRTCP` |
| Session | `srtp_create` / `srtp_dealloc` (libsrtp-style) |
| Primitives | OpenSSL: AES-128/192/256 (CBC/CFB/ECB/OFB), 3DES, MD5, SHA-1, HMAC, RSA, DSA, DH, RC4, PBKDF2 |
| Config | `disSRTPEnable`, `disSrtpAuthenOffer`, `CLIENT_MASTER_KEY`, `clearRTPMasterKey`, `clearSrtpCytptoSuite`, `ccGetConnectionCrypto` |

Implications for `mod_mgcp`:

- **Default is plaintext RTP** — encryption only engages if the Call Agent offers
  `a=crypto:` in the CRCX SDP. Our current SDP (PCMU on 5004, no crypto line)
  keeps the call unencrypted, which is correct for now.
- **To enable encryption later**: advertise `AES_CM_128_HMAC_SHA1_80` and add the
  SDES `a=crypto:` line to the CRCX SDP; FreeSWITCH's `libsrtp` interoperates
  directly (the suite is standard). No proprietary cipher to reverse-engineer.
- **SDES sends the key in the clear** inside SDP, so SRTP is only as secure as
  the MGCP signaling path — real security needs TLS on the signaling channel.

## 11. Media path in mod_mgcp (current state)

- CRCX SDP offers `m=audio 5004 RTP/AVP 0` + `a=rtpmap:0 PCMU/8000` with
  `L: p:20, a:PCMU` and `M: sendrecv` — matches the phone's `CODEC_PCMU`
  capability (phone also supports PCMA, G729A, G722, BV16/32).
- Dial tone is generated by the phone's own DSP once the RTP path is up
  (we do NOT send the tone — `S: L/dl` just opens the audio path).
- For a bridged call, the module must relay RTP on port 5004 to a FreeSWITCH
  media session (and offer `a=crypto:` if SRTP is wanted). This is the only
  media-side work remaining; the signaling/SDP handshake is already correct.
