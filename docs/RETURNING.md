# RETURNING.md — restart guide for a future maintainer

Status: checkpoint guide · 2026-09-29.
Written for someone arriving **6–24 months later**, possibly not the original author.

---

## ⚠️ Read this first: there is no verified clean-start path

**The stack has never been brought up from the repository on a clean machine.** The
generator and bring-up script exist and are described as idempotent, but two of the
most important services run as host development processes rather than containers, and
their configuration lives in host `.env` files outside the declarative tree. Treat
every command below as *the best current understanding*, not as a tested procedure.

**Bounded remediation task (do this before trusting anything else):**

> **TASK R5-01 — clean-host bring-up.** On a machine that has never run this stack,
> follow §4 using only the repository and the secrets material. Record every deviation
> as you go. Success = the sign-in page loads and one authenticated request succeeds.
> Time-box to one day. Do not "fix" it by copying files from the production host.

Until that task is done, the honest status of deployment reproducibility is
**Partially implemented** (`REALITY.md` row 1).

---

## 1. What to read first, in this order

1. `HIBERNATION-NOTE.md` — what the project is, why it is paused, what not to infer.
2. `docs/REALITY.md` — **what actually works**, with evidence and honest labels.
3. `docs/DECISIONS.md` — what is settled vs open, so you do not re-litigate it.
4. `docs/RISKS.md` — especially R-01 (bus factor), R-07 (no backup), R-16 (images exist
   only on the production host).
5. `STATUS.md` — historical, **stale**; useful for narrative, not for facts. `REALITY.md`
   supersedes it.
6. `AGENTS.md` — operational conventions and known quirks. Also stale in places.

Do **not** start by reading the ~79 documents in `docs/design/`. They describe intent,
much of which is unbuilt.

## 2. How to identify the active repository

- There is **one** repository: the directory you are in, whose remote is a *personal*
  GitHub account (not an organization), default branch `main`.
- Verify you have the right one: `git log -1 --format='%H %an %ad %s'` and confirm
  `docs/REALITY.md` exists — it was added at the checkpoint and is the marker of this era.
- There are no tags and no releases. The commit that adds `HIBERNATION-NOTE.md` is the
  checkpoint boundary.
- A timestamped git bundle may exist outside the repository; check
  the backups directory on the production host before assuming history is lost.

## 3. Prerequisites

| Need | Version seen at checkpoint |
|---|---|
| Node.js | v26.7.0 |
| npm | 11.19.0 |
| Python | 3.14.7 |
| `uv` | 0.12.3 (used to run the generator with a pinned PyYAML) |
| Docker + Compose | required for every pillar |
| Access | the host itself; there is no remote deploy path |

Dependency install: this is an npm-workspaces monorepo (`apps/*`, `contracts`), but
several apps also carry pnpm lockfiles. **Check which package manager an app actually
uses before running an install in it.**

## 4. Safest known startup procedure

Run these in order. Every step is observable; stop at the first one that misbehaves.

1. **Confirm the secrets material exists — without printing it.** The derived-key
   master file must be present with mode `0600`, and a vault password file must exist.
   If either is missing, stop: nothing else will work, and R-02 applies.
2. **Generate the deployment artifacts from the tree.**
   `uv run --with pyyaml python infra/build/generator.py dev`
   *Note:* the generator deletes the entire generated output directory on every run.
   Never keep an artifact you cannot rebuild there.
3. **Validate one pillar statically, before starting anything:**
   `docker compose -f infra/out/dev/compose/<pillar>/docker-compose.yml config`
4. **Bring up the pillars:** `bash infra/scripts/stack-up.sh`
   This is also what the systemd unit runs at boot. It exits non-zero if any project fails.
5. **Start the two host processes** — these are *not* part of the bring-up script and
   the stack is not functional without them:
   - the API: `npm run dev:api`
   - the dashboard: `npm run dev:web`
6. **If you regenerate the edge config, restart the edge.** The edge's file provider
   does not pick up atomic rewrites of the generated routing file. This is a known,
   expected step — it is not a symptom of breakage.

## 5. Tests, linting, type checks

- `make test` → `infra/scripts/journeys.sh`. This is the only E2E entry point. It runs
  browser journeys covering sign-in, membership, group scoping, is NOCODB read/write,
  mail, search, ERP SSO, and anonymous isolation. Credentials are derived in memory from
  the master key — the suite needs the stack to be **up**.
- Contracts: `npm run test:contracts` / `npm run compile:contracts` at the root.
- The dashboard is the only project with CI (`.github/workflows/irl-dashboard-build.yml`,
  lint + build). **There is no CI for the API, the contracts, or the infrastructure.**
- There is no separate lint or type-check target at the root. Run the app-level scripts
  directly and expect surprises.

## 6. Inspecting configuration without exposing secrets

- Read the **instance tree** (`infra/instances/dev/`) — that is the declared intent and
  contains no plaintext secrets, only references.
- Read what the generator *produced* under `infra/out/dev/` — but note it **does**
  contain resolved secret values. Do not print it, screenshot it, or paste it into chat.
- To check whether a variable is set, check for its presence — never echo the value:
  e.g. test a variable is non-empty rather than printing it.
- External secrets live in an encrypted vault in the repository (ciphertext). View them
  only with the vault password file, and never into shared output.

## 7. What is known to work vs unverified

**Known to work (verified at the checkpoint):** sign-in through the single issuer;
group creation and resource scoping; row-level isolation for the coop schema; the files
panel; mail on all four ports; the project tool's zero-click SSO; the declared-vs-running
status report.

**Not verified / not built:** clean-host bring-up; a real person's invite-and-onboard
journey; effective access shown in one place; any money movement; the on-chain
relationship graph; nested groups; agent write tools; backup and restore.

Full detail, domain by domain, is in `REALITY.md` — that table is the source of truth.

## 8. First five restart tasks (small and observable)

1. **Read `HIBERNATION-NOTE.md` and `docs/REALITY.md`.** No commands. Expect ~20 minutes.
2. **Confirm the repository is intact.** `git log -1`, `git status`. Confirm
   `docs/REALITY.md` and `HIBERNATION-NOTE.md` exist. Success is observable: both files
   present, history intact.
3. **Confirm the secrets material exists and is correctly permissioned** — presence and
   mode only, never contents (see §6).
4. **Generate and statically validate** (§4 steps 2–3). Success = the generated tree
   appears and compose validates for at least one pillar.
5. **Bring up the edge pillar alone** (§4 step 4, one pillar) and confirm it terminates
   TLS for one hostname. Do not start the whole stack as your first move.

## 9. First five things not to change without a design review

1. **The seat model.** How a membership row identifies its holder is an open, load-bearing
   decision (D-16). Changing it silently would invalidate every explanation in these docs.
2. **Row-level security policies and their helper functions.** They are the actual data
   boundary; the application is not.
3. **The derived-key scheme.** Rotating the master key rotates *everything* and will
   invalidate every credential derived from it.
4. **The generated edge configuration.** Regenerate; never hand-edit generated output.
5. **Anything touching money.** No rail is enabled, no chain is chosen (D-21), and the
   custody design is unresolved. Adding a rail would create a real-world financial system
   on top of an untested design.

## 10. When in doubt, do this

- **Believe the code over the documentation**, then write down the contradiction.
- **Regenerate rather than hand-edit.**
- **Do not start services or change configuration on the production host** without asking
  whoever now holds it.
- **Do not commit secrets**; check whether a file is ignored before adding it.
- **Prefer a smaller proof.** A narrow thing demonstrated beats a wide thing claimed.
- **If a claim has no test, deployment record, or reproducible procedure behind it, label
  it unverified** — even if it is in a design document.

## 11. Minimum proof before a public pilot

- [ ] A clean host brings the stack up from the repository alone (R5-01).
- [ ] A restore from backup has succeeded at least once (R-07).
- [ ] One real person has been invited, joined, and reached the group's home (§8 task 2).
- [ ] Row-level isolation has been re-verified on a freshly created group.
- [ ] Every subsystem the pilot touches is labelled in `REALITY.md` — no unknowns.
- [ ] The pilot's feature boundary in `FIRST-PILOT.md` excludes money, custody,
      telephony, and agent writes.
- [ ] A named successor or custodian exists (R-01 / D-29), or the pilot is explicitly
      accepted as non-continuable if the maintainer disappears.