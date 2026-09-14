# eSIM and remote SIM: can numbers live on virtual devices?

**Question (Robbie, Sep 2026):** is there a way to do eSIMs connected to virtual devices?
**Short answer:** the **numbers** can be virtual — profiles managed as software, no plastic, no phone.
The **radio** cannot. And the architecture that separates a SIM from its radio is a *documented fraud
signature*, which decides how it may be used. Checked 2026-09-13; sources at the end.

## What is genuinely possible, self-hosted

**1. An eUICC in your own hardware, managed from Linux — `lpac`.**
`lpac` (estkme-group) is an open-source **LPA** implementing GSMA **SGP.22 v2.2.2**: list, enable,
disable, delete, nickname, download and discover profiles, read chip info, and send a custom IMEI to
the SM-DP+ server. It speaks APDU over **PCSC** (a card reader) or over a modem's **serial AT
interface** (`$LPAC_APDU=at`, `$AT_DEVICE=/dev/ttyUSB0`). It builds and runs on a Raspberry Pi.

That is the whole answer to "eSIM on a virtual device" in the part that is real: **an M.2 or USB LTE
module with an eUICC — embedded, or a removable eUICC card in the module's SIM socket — provisioned
and switched from a server, with no phone involved.** Numbers become *profiles* you hold and swap in
software.

Hardware that exists: M.2 LTE modules with **built-in eSIM and SMS capability** appear on carriers'
own *approved module* lists (e.g. Quectel EM060K-GL on Verizon Open Development), and industrial
**16- or 64-slot 1U LTE SMS gateways** (Quectel modules, chassis with per-channel power switching)
are sold for exactly this. `ModemManager`/`gammu`/TextBee then serve SMS into
`apps/coop-api/src/sms.ts`.

**2. SIM cards separated from their modems — `osmo-remsim`.**
Osmocom's remote-SIM suite "lets you operate an entire fleet of modems/phones, as well as banks of
SIM cards, and dynamically establish or remove the connections between them": `remsim-bankd` holds
real cards, `remsim-client` presents an **emulated SIM** to a modem (via SIMtrace hardware running
`cardem` firmware), and `remsim-server` owns the mapping. A modem therefore sees a SIM that is
physically somewhere else, and which SIM it sees can change at runtime.

**3. What does not exist:** a profile with no secure element. An eUICC is a secure element and the
carrier's SM-DP+ only provisions to a certified one, so there is no "eSIM in a VM". Everything sold
as that — including the SIM-backed verification services in the cost comparison — is **a modem farm
in someone else's datacentre**, rented by the code. The radio is the irreducible hardware.

## The constraint that decides how it may be used

This is the part worth reading twice. **A bank of consumer SIMs driving modems is SIM boxing**, and
the carriers' own published terms name it:

- **AT&T** restricts unlimited voice to *"live dialogue between individuals"* and expressly prohibits
  commercial use, capping non-dialogue use at 1,000 minutes/month.
- **T-Mobile** prohibits uses *"designed for unattended use, automatic data feeds, automated
  machine-to-machine connections"* and prohibits resale of the service.
- **Verizon** reserves the right to limit, suspend or end service for resale, *"spam, or engag[ing] in
  other abusive messaging or calling."*

And they do not merely forbid it — they **detect it**. GSMA `FS.01.1` documents SIM-box bypass and the
detection mechanisms; the NDSS paper *Preventing SIM Box Fraud* proposes access control using
control-plane **device fingerprints** plus a coarse **plan-type** rule ("phone plans should not be
allowed for non-registered IoT devices"); and *SigN* names the specific tell:

> "No other user end device (smartphones, tablets, laptops, IoT devices, modems, etc.) separates the
> SIM card from the Mobile Equipment during network operations, making **remote SIM card
> association an explicit proxy for advanced SIMBox activity**."

So `osmo-remsim`'s clever part — the SIM decoupled from the radio over IP — **is itself the signature
they look for**, detectable in attachment signalling. The evasion documented in the wild (swapping
SIMs, rewriting IMEIs) is a treadmill, not an architecture.

**And for this repo there is a sharper consequence than compliance.** A terminated SIM takes the
*account* with it: lose the number and you lose the group's 2FA. **Number legitimacy is account
durability.** That is why the next paragraph is the actual recommendation rather than a disclaimer.

## The legitimate route, which the literature also names

The same NDSS paper notes MNOs want *lawful* gateway deployments **pre-registered** (citing T-Mobile's
bring-your-own-device registration), and carriers publish approved modules for exactly this. So:

1. **Get the gateway into the contract, not around it.** Ask the carrier for an **M2M / business**
   SIM and plan for a registered gateway in approved hardware — an M.2 module with eUICC on their list,
   or a 1U SMS gateway. Then remote-SIM and profile management are legitimate engineering.
2. **Split the two number roles — they have incompatible requirements.**
   - *Verification and 2FA numbers*: must be **mobile-class** (see the cost comparison: Instagram
     rejects VoIP/M2M-class ranges at entry). A phone-class number lives legitimately in a phone-like
     device — which is why **one Android + TextBee per group** is not a stopgap but the *correct*
     answer at small scale.
   - *Coop infrastructure numbers* (voice, IVR, member notifications): **carrier-approved modems +
     IoT/business SIMs**, API-managed, and free of the verification constraint entirely.
3. **Scale the phone path until it hurts, then scale with a contract.** ~10–30 groups on Android
   devices is ordinary phone use, $8/mo per number, zero engineering, and it passes verification.
   Past that, the modem bank is right — *with the carrier's agreement*, on device-licensed SIMs, and
   with the acknowledgement that verification numbers still need phone-class service.

## What this would look like here

| layer | choice |
|---|---|
| radio | M.2 LTE modules (eUICC onboard) in a chassis, **on the carrier's approved list** |
| profiles | `lpac` over the modem's AT interface — enable/disable/switch without touching hardware |
| SIM ↔ modem mapping | local (module's own SIM) by default; `osmo-remsim` only if pooling is needed and the carrier knows |
| SMS serving | `ModemManager`/`gammu` → TextBee → `POST /api/v1/internal/sms/inbound` (already built) |
| the constraint | a **registered** gateway on an **M2M/business** plan; phone-class numbers stay in phones |

## Open decisions

1. **Ask a carrier the real question** — "business/M2M SIM with SMS enabled, in approved hardware, on a
   gateway we register with you" — and record the answer. It decides whether the bank path exists at
   all, before any hardware is bought.
2. **Test the eSIM path small**: one M.2 module + one removable eUICC + `lpac` on a spare machine, to
   prove profile switching end to end without a phone.
3. **The hardware inventory belongs in `did-inventory-forecasting.md`** — that document currently
   counts numbers; the modem/SIM/device count is the same question and should live beside it.

## Sources

| what | source | read |
|---|---|---|
| osmo-remsim: fleet of modems, SIM banks, dynamic mapping; virtual SIM via SIMtrace cardem | github.com/osmocom/osmo-remsim, osmocom.org/projects/osmo-remsim, osmo-remsim user manual | 2026-09-13 |
| lpac: open-source LPA, SGP.22 2.2.2, AT backend, chip/profile/notification mgmt, Raspberry Pi | github.com/estkme-group/lpac (docs/USAGE.md), manpages.debian.org, simplexwireless.com | 2026-09-13 |
| SIM boxing: consumer terms quoted; detection; remote SIM association as the signature | sipnex.ca/blog/sim-gateway-vs-sip-trunk, GSMA FS.01.1, ndss-symposium.org *Preventing SIM Box Fraud*, arxiv.org/html/2502.01193 (SigN) | 2026-09-13 |
| M.2 modules with built-in eSIM + SMS on a carrier approved list | opendevelopment.verizonwireless.com approved modules (Quectel EM060K-GL) | 2026-09-13 |
| 16/64-slot LTE SMS gateways | madcom.uk multichannel modems | 2026-09-13 |
