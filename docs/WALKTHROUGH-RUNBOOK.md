# WALKTHROUGH-RUNBOOK.md — continuity recording

Status: checkpoint runbook · 2026-09-29.
Purpose: a raw, unpolished screen recording that carries context no document can —
what the system looks like, how the author thinks about it, and what is genuinely
unknown. **Target length: 20–30 minutes. One take is fine. Polish is not the point.**

Record it before the hibernation gap, not after. A recording made by somebody
reconstructing the system from documents is worth far less than one made by the person
who built it.

---

## Before you press record

- Close every editor tab and browser tab that is not part of the walkthrough.
- Close any terminal that has printed a secret.
- Have `docs/REALITY.md`, `docs/DECISIONS.md`, and `docs/RISKS.md` open in a viewer
  — you will read from them rather than recall.
- Do a two-minute test recording for audio levels, then delete it.

## Do not show on camera

**This list is the most important part of this document.** Read it before recording.

- Any `.env` file, and any file whose name ends `.env`, `.env.local`, or similar.
- The generated deployment output directory — **it contains resolved secret values.**
- The secrets directory: the master key, the vault password file, any certificate
  private keys, any ACME account state.
- The vault file's *decrypted* contents. Showing the encrypted file's existence is fine;
  its plaintext is not.
- Any terminal history, shell prompt scrollback, or editor buffer showing credentials,
  tokens, or connection strings. Start a fresh terminal.
- Any provider dashboard: no carrier console, no registrar console, no cloud console,
  no payment provider console, no code-hosting settings pages.
- Any billing page, card number, invoice, or account-recovery screen.
- The host's real network addressing: no public address, no router administration page,
  no tunnel/admin UI, no network map with addresses, no port-forwarding table.
- Any member's real personal data — names, email addresses, phone numbers, or a live
  member list from a real group. Use a scratch group and pseudonyms.
- Any private key, seed phrase, or wallet screen, in any form, at any zoom level.
- Browser password managers, autofill dropdowns, or saved-login lists.

If something sensitive appears on screen by accident: **stop, delete the recording,
and start again.** Do not attempt to cut it out.

---

## Outline (20–30 minutes)

### 1. Mission and status disclaimer — 3 min
Say plainly: what IRL.coop is for, that it is under active development, that it is **not**
production-ready and **not** a fully integrated platform, and that code present does not
mean feature working. State that a future viewer should trust `docs/REALITY.md` over
anything said on camera. Name today's date and that this is a hibernation checkpoint.

### 2. Repository tour — 4 min
Walk the top level. Which directories matter: the declarative instance tree, the build
generator, the two first-party applications, the contracts, the scripts, and the design
documents. Say out loud how many design documents there are and that the design is far
ahead of the code. Point at the checkpoint files as the entry point for a newcomer.

### 3. How to recognise the entry points — 2 min
Show, do not describe: the API's entry module, the dashboard's application root, the
declarative instance definition, the generator, and the bring-up script. Explain the one
sentence that matters: *the tree is the source of truth, the generator emits the
artifacts, and generated output is never hand-edited.*

### 4. Development and deployment overview — 3 min
How the stack is meant to come up. Be explicit about the two host development processes
that are **not** part of the bring-up script, and about the regeneration step that
requires an edge restart. Say that a clean-host bring-up has never been performed —
this is the honest state and the most likely thing to bite whoever returns.

### 5. Data stores and integrations at a high level — 3 min
One relational database with row-level security as the enforcement point, one cache,
one object store, and a set of third-party applications that each consume the same
identity. Explain the projection-vs-truth split: the database is a rebuildable
projection; the chain is meant to be the truth layer. Say which integrations are
verified and which are not.

### 6. Authentication and authorisation: intention vs reality — 3 min
The intention: one issuer; every account a Safe; access declared through seats; nothing
inherited. The reality: seats are keyed to a person, not a Safe; the on-chain
relationship registry is a skeleton with a placeholder function; nested groups are not
representable yet. This is the section most worth recording — it is where intention and
code diverge most, and it is hard to reconstruct from documents alone.

### 7. What is known to work — 3 min
Sign-in through the single issuer; group creation and scoping; row-level isolation with
a test behind it; documents and files; mail; the project tool's SSO; the status report.
For each, name the evidence: a test, a verification run, or a deployment record.

### 8. What has never been demonstrated — 3 min
That a real person can be invited and onboarded; that a real group can complete a piece
of work; any money movement; the on-chain graph; backup and restore; a clean bring-up.
Say the uncomfortable part: the "demonstrated in a real group workflow" label is used
zero times in `REALITY.md`.

### 9. Biggest risks — 3 min
Walk `RISKS.md` top to bottom out loud, and say which three you would fix first and why.
Include the organisational ones — one maintainer, no successor, no organization holding
the accounts — not just the technical ones. This is the part a future maintainer most
needs to hear in your voice.

### 10. First recommended restart task — 1 min
The first thing to do on return, and why it is first. Point at the bounded remediation
task in `RETURNING.md` and say what "done" looks like.

### 11. Where decisions and the inventory live — 1 min
Point at the decision register, the risk register, the operations inventory, and the
reality map. Say which one to read first and which to trust when they disagree.

### 12. Closing — 1 min
Who you are, what you would do next if you had another month, and an honest sentence
about what you are unsure of. Address the recording to whoever finds it.

---

## After recording

- Store the file somewhere that survives the host — **not** only on the production
  machine or in a gitignored directory.
- Note its location in the operations inventory.
- Do not edit it into a polished video. Its value is that it is raw and true.
- If a second person appears, record a short follow-up with them: what they would need
  in order to continue.