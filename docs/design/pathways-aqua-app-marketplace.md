
# Pathways + Aqua for the app marketplace

**Status: design · 2026-11-20.**

This document shows how Pathways (accountable workflow execution) and Aqua
(cryptographic attestation) make the app marketplace safer, auditable, and
autonomous. Not theory — concrete integration points.

## Quick recap: the two primitives

| Primitive | What it is | From |
|---|---|---|
| **Pathways** | Every workflow is a versioned, signed, auditable run with autonomy levels (A1-human, A2-headless, A3-peer-gated) | DJ Thomson's design |
| **Aqua** | Cryptographic provenance: every artifact is hashed, signed, and its lineage preserved in an immutable tree | BFI / Aqua Protocol |

Together: Pathways governs *how* work happens; Aqua proves *what* happened.

---

## 1. App review as a Pathway run (not a meeting)

**Current state:** A developer opens a PR. App-stewards review in comments.
Someone merges. The decision lives in GitHub history. If a steward is
compromised or coerced, there is no cryptographic proof of who approved what.

**Pathways state:** App review is a `review-app` pathway template. Every
blessing is a PathwayRun.

```yaml
# pathways/templates/review-app.yaml
name: review-app
version: 1.0.0
autonomy: A2  # headless with gate-profile enforcement
triggers:
  - type: pull_request
    repo: irl-coop-stack-v2
    path: apps/proposals/**
steps:
  - name: lint-and-test
    executor: ci-runner
    script: make test APP=$app_name
  - name: security-scan
    executor: trivy-scanner
    script: trivy image $image_digest
  - name: reproducibility-check
    executor: build-runner
    script: make build-twice-compare-digests APP=$app_name
  - name: steward-approval
    executor: safe-vote
    config:
      safe_address: app-stewards.safe.irl.coop
      threshold: 2
      proposal: "Bless $app_name at commit $git_commit, digest $image_digest"
  - name: on-chain-blessing
    executor: base-transaction
    script: CoopRegistry.blessApp(name, gitCommit, imageDigest, trustTier)
```

**What this gives you:**
- **Every blessing is a signed artifact.** The PathwayRun ID is published.
  Anyone can look up: who triggered it, what tests ran, how the steward vote
  was cast, what transaction landed on-chain.
- **Coercion resistance.** A steward under duress cannot silently bless a
  malicious app — the Safe threshold requires multiple signatures, and the
  PathwayRun proves the vote occurred at a specific time with specific
  participants.
- **Forkability.** A dissenting steward who believes the process was corrupted
  can fork the PathwayRun, publish an alternate audit trail, and the network
  can see both versions.

---

## 2. Aqua attestation for every build artifact

**Current state:** Docker images are (sometimes) pinned by digest. But the
build process itself is not attested. A CI runner could be compromised and
produce a malicious image with a valid-looking digest.

**Aqua state:** Every build produces an AquaTree — a Merkle tree of every
input file, every dependency, every build step output.

```
AquaTree for app "soil-sensor-hub" v1.2.3:
  root: sha256:aqua_root_abc...
  leaves:
    - Dockerfile                     → sha256:leaf_001...
    - src/main.py                    → sha256:leaf_002...
    - requirements.txt               → sha256:leaf_003...
    - base image: ubuntu@sha256:xyz  → sha256:leaf_004...
    - build output: image.tar        → sha256:leaf_005...
    - test results: junit.xml        → sha256:leaf_006...
    - CI runner identity cert        → sha256:leaf_007...
  signatures:
    - CI runner: sig_ci_runner...
    - Reproducibility verifier: sig_repro...
    - App-stewards Safe: sig_safe...
```

**What this gives you:**
- **Verifiable builds.** A node operator can download the AquaTree, recompute
the Merkle root, and verify that the image they received matches the one the
CI system produced.
- **Supply chain transparency.** If `requirements.txt` depended on a malicious
PyPI package, the AquaTree records exactly which version was fetched. Post-hoc
audits trace the compromise to a specific leaf.
- **No need to trust the CI runner.** The runner signs its output, but the
signature is only valid if the Merkle root matches. A compromised runner
cannot forge a valid signature for a tampered artifact.

---

## 3. Node installation as a gated Pathway run

**Current state:** An operator clicks "Install" in the dashboard. The backend
calls `docker compose up -d`. There is no audit trail of who installed what
when.

**Pathways state:** Installation is a `node-install-app` Pathway run at
autonomy level A2 — headless, but with a gate-profile that enforces policy.

```yaml
# pathways/templates/node-install-app.yaml
name: node-install-app
version: 1.0.0
autonomy: A2
gate_profile:
  allow_only_blessed: true  # refuse self-hosted apps unless operator overrides
  max_trust_tier: 2          # refuse experimental (tier 1) apps in production
  require_aqua: true         # refuse apps without AquaTree attestation
triggers:
  - type: dashboard_action
    action: install_app
steps:
  - name: verify-blessing
    executor: on-chain-read
    script: |
      blessing = CoopRegistry.getBlessing($app_name)
      assert blessing.approvedAt > 0
      assert blessing.trustTier <= $gate_profile.max_trust_tier
  - name: verify-aqua
    executor: aqua-verifier
    script: |
      tree = Aqua.downloadTree($app_name, $version)
      assert Aqua.verifyRoot(tree, $expected_root)
      assert Aqua.verifySignature(tree, app_stewards_safe)
  - name: fetch-image
    executor: docker
    script: docker pull $image_digest
  - name: verify-image-digest
    executor: sha256
    script: |
      actual = docker inspect $image_id --format='{{.RepoDigests}}'
      assert actual == $image_digest
  - name: regenerate-compose
    executor: generator
    script: python3 infra/build/generator.py dev
  - name: apply
    executor: docker-compose
    script: docker compose up -d $app_name
  - name: notify-bus
    executor: event-publisher
    script: bus.publish({type: 'app_installed', app: $app_name, node: $node_id, run: $pathway_run_id})
```

**What this gives you:**
- **Policy enforcement by code, not by trust.** The gate-profile is a signed
artifact. A compromised operator account cannot override it without the Safe
threshold.
- **Every installation is auditable.** The PathwayRun records exactly what
was checked, what passed, what failed. If an operator later claims "I didn't
install that app," the run ID proves otherwise.
- **Network-wide visibility.** When a node installs an app, the event bus
publishes it. Other nodes see: "Node-47 just installed soil-sensor-hub v1.2.3
(run pr_0xabc...)." This is how the network learns which apps are trending,
which are abandoned, which have been installed by trusted peers.

---

## 4. Self-hosted app validation, not prohibition

**Current state:** Self-hosted apps run without validation. The dashboard
warns but does not enforce. A group can install anything, including malware.

**Aqua state:** Self-hosted apps are **not blocked**—they are **attested**.
The group uploads their app spec and (optionally) an AquaTree of their build
process. The dashboard shows:

```
App: bespoke-crm
  Type: self-hosted
  AquaTree: uploaded 2026-11-15, signed by 0xBespokeDevSafe
  Build reproducibility: verified (CI ran twice, digests matched)
  Last security scan: 2026-11-18 (Trivy: 0 critical, 2 medium)
  Federation compatibility: untested
  Trust: this group vouches for it; no canonical blessing

  [Install anyway] [View AquaTree] [Reject]
```

**What this gives you:**
- **Self-hosted apps can still be trustworthy.** A group that invests in
 reproducible builds and security scans gets a green badge. A group that
 uploads a black-box image gets a red badge. The operator decides, but the
data is there.
- **Federated groups can set policies.** "Our node will only accept self-hosted
apps from groups whose Safe has a trust score above 50." The Pathways
gate-profile can express this.
- **Graduation pathway.** A self-hosted app with 100 verified installations
and zero security issues can be proposed for canonical blessing. The Pathway
review process already has the AquaTree and CI history.

---

## 5. Pathways HandoffEnvelope as the app distribution format

**Current state:** Apps are distributed via Docker Hub, GitHub releases, or
custom registries. These are centralized, censorable, and opaque.

**Pathways state:** The canonical distribution format is a `HandoffEnvelope`:

```json
{
  "handoff_type": "app_distribution",
  "app_name": "soil-sensor-hub",
  "version": "1.2.3",
  "git_commit": "abc123...",
  "image_digest": "sha256:xyz...",
  "aqua_tree_cid": "QmAbc...",  // IPFS content-addressed AquaTree
  "blessing": {
    "approved_by": "app-stewards.safe.irl.coop",
    "approved_at_block": 18402391,
    "trust_tier": 2
  },
  "source": {
    "repo": "https://github.com/irlcoop/soil-sensor-hub",
    "release_url": "https://github.com/.../releases/tag/v1.2.3"
  },
  "safe_signature": "0x...",
  "pathway_run": "pr_0x7a3f..."
}
```

**Distribution flow:**
1. App-stewards bless the app. The PathwayRun produces the envelope.
2. The envelope is pinned to IPFS (or stored on the event bus).
3. Nodes discover new apps via the event bus or by querying the on-chain registry.
4. A node operator downloads the envelope, verifies the Safe signature,
   fetches the AquaTree from IPFS, verifies the image digest, and installs.

**What this gives you:**
- **No central registry.** The app marketplace is a peer-to-peer gossip of
 signed envelopes, not a single server.
- **Censorship resistance.** An app cannot be delisted globally unless the
 on-chain blessing is revoked by the Safe threshold. Even then, nodes that
 already have the envelope can continue to install it.
- **Offline distribution.** A field worker at a rural node can receive the
 envelope via Bluetooth, verify the signature with no internet, and install
 the app.

---

## 6. Revocation as a Pathway run with emergency autonomy

**Current state:** If Keycloak has a CVE, someone manually updates, someone
else manually warns operators. There is no coordinated global response.

**Pathways state:** Revocation is a `revoke-app` Pathway run with a special
autonomy level: A1-emergency (headless, but with a 24-hour human veto window).

```yaml
name: revoke-app
version: 1.0.0
autonomy: A1-emergency
gate_profile:
  emergency_window_hours: 24
  veto_threshold: 1  # any steward can veto within 24h
triggers:
  - type: cve_alert
    severity: critical
steps:
  - name: verify-cve
    executor: osv-scanner
    script: osv query --app $app_name --version $version
  - name: confirm-blessing-exists
    executor: on-chain-read
    script: assert CoopRegistry.blessedApps[$app_name].approvedAt > 0
  - name: propose-revocation
    executor: safe-vote
    config:
      safe_address: app-stewards.safe.irl.coop
      threshold: 2
      proposal: "Revoke $app_name due to CVE-$cve_id"
  - name: publish-revocation-envelope
    executor: event-publisher
    script: |
      bus.publish({
        type: 'app_revoked',
        app: $app_name,
        reason: 'CVE-$cve_id',
        pathway_run: $run_id,
        veto_window_closes: now() + 24h
      })
  - name: wait-veto-window
    executor: timer
    script: sleep 24h
  - name: execute-if-not-vetoed
    executor: base-transaction
    condition: veto_count == 0
    script: CoopRegistry.revokeApp($app_name, $cve_id)
```

**What this gives you:**
- **Fast response.** The Pathway triggers automatically on CVE alert. No human
 meeting needed.
- **Democratic emergency brake.** Any steward can veto within 24 hours. This
 prevents a compromised steward from weaponizing revocation.
- **Network-wide notification.** Every node receives the revocation envelope
 before the on-chain transaction finalizes, giving operators a head start to
 uninstall.
- **Audit trail.** The entire emergency response — who proposed, who voted,
 who vetoed (if anyone) — is preserved in the PathwayRun.

---

## Summary: where Pathways + Aqua add value

| Problem without Pathways/Aqua | How Pathways + Aqua solve it |
|---|---|
| App review is an unrecorded meeting | Review is a signed, auditable PathwayRun |
| Build provenance is opaque | Every build has an AquaTree with Merkle proofs |
| Node installation is unlogged | Installation is a gated Pathway run with policy enforcement |
| Self-hosted apps are unvalidated | Self-hosted apps get voluntary AquaTree attestation |
| App distribution is centralized | HandoffEnvelope is peer-to-peer, signed, censorship-resistant |
| Revocation is ad-hoc | Revocation is an emergency Pathway run with democratic veto |
| No global visibility into what nodes run | Event bus publishes every install/revocation as a signed event |

---

## The honest limits

| Limit | Why |
|---|---|
| AquaTree upload is optional for self-hosted | We cannot force groups to attest. The system incentivizes it via trust scores. |
| Pathways runs cost gas | On-chain blessing/revocation costs Base L2 gas (~$0.01/tx). The irl.coop steward treasury subsidizes app-stewards operations during the pilot. |
| IPFS pinning is not guaranteed | If no one pins the AquaTree, it becomes unreachable. Popular apps are pinned by many nodes; obscure apps may need their developer to maintain a pin. |
| 24-hour veto window is a long time for a CVE | The `A1-emergency` autonomy can be tuned. For truly critical vulnerabilities, the threshold could be lowered to 1-of-3 with a 1-hour window. |

---

## One-line summary

Pathways turns app governance into accountable, auditable workflows. Aqua turns
build artifacts into cryptographically-verifiable provenance. Together, they
replace "trust the maintainer" with "verify the math."
