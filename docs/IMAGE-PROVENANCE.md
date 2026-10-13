# Image provenance — what can be rebuilt, and the path to owning the source

**Status: measured 2026-10-12/13.** Replaces the vague "51 first-party images exist only on
this host" with what is actually true, per image, and lays out the path to forking the source
into the monorepo.

## 1. The real numbers

| | Count |
|---|---|
| `irlcoop/*` **tags** on the host | 51 |
| **Distinct images** | 21 |
| **Deployed** by the app specs (`infra/instances/dev/apps/*.yaml`) | **20** |
| …of which **fully reproducible from this tree** | 12 |
| …of which **need a pinned upstream fetched at build time** | 5 |
| …of which **cannot be rebuilt from this repo at all** | **2** (+ the `rag-*` base) |

The 51 figure counted tags, not images: `nocodb-gate-sso` alone carries **15** historical
tags, `formbricks-gate-sso` 7, `hievents-gate-sso` 4, `postiz` 3, `rag-api` 3. The exposure
is two images, not fifty-one. Stale tags can be pruned freely (a deploy is pinned by tag in
the spec, and the running tag of every app is listed above).

## 2. The build pattern already in use

Every forked image follows one shape, and it is a good one:

> **clone upstream at a pinned SHA → apply an in-tree patch → build**

The **patch is ours and lives in this repo**. The **upstream tree is not** — it is fetched
over the network at build time. Examples of the pinned inputs, all recorded in the build
scripts themselves:

| Image | Upstream | Pin |
|---|---|---|
| `formbricks-gate-sso` | `formbricks/formbricks` | commit `286958e36464663489bfbc73d87abbd0f573825f` (the 5.4.0 tag) + 3 patches in `infra/build/images/formbricks/` |
| `hievents-gate-sso` | Hi.Events | patch at `infra/instances/dev/assets/hievents/irlcoop-gate-sso.patch` |
| `webstudio-builder-gate-sso` | `webstudio-community/webstudio-fork` | branch `develop` @ `da1f9bb98a002f7d13232fcc448cb6da70f6fc0d` + `infra/instances/dev/assets/webstudio/gate-sso.patch` |
| `postiz` | Postiz | `infra/build/images/postiz/irlcoop-fork.patch` |
| `nocodb-gate-sso` | **our fork** `rbpollock/nocodb` | branch `irlcoop` (rebased onto the team's Aug 13 develop tip), `Dockerfile.irlcoop` at the fork root |

## 3. Classification

**A — reproducible from this tree (12).** Build context and every source file are in the repo;
only base images are pulled.

`browser-runner` · `embed-rerank` · `llm-inference` · `plane-mcp` · `postgres-citus` ·
`synapse-s3` · `roundcube-oidc` · `wordpress` · `cinny` (pinned tag + in-tree
`apply-patch.mjs`) · `fusionpbx` (pinned tag + in-tree Php files) · `freeswitch` (four pinned
upstream clones + in-tree `entrypoint.sh`) · `element-web` (pinned upstream release tarball)

**B — patch in the repo, upstream fetched at build time (5).** Rebuildable **while the pinned
upstream SHA and URL remain reachable**.

`formbricks-gate-sso` · `hievents-gate-sso` · `postiz` · `litefarm-api` + `litefarm-web`
(`infra/build/images/litefarm/build.sh`) · `webstudio-builder-gate-sso`

**C — cannot be rebuilt from this repo (2).**

- **`nocodb-gate-sso`** — the fork is at `github.com/rbpollock/nocodb`, **outside the
  monorepo**, and the image additionally carries **two pre-built minified nc-gui chunks** that
  were *not* built from the fork's source (the `CthfTbo6.js` base-list chunk and the
  chatwoot-removal chunk). Those are binaries with no source path today.
- **`rag-api` / `rag-worker`** — **RECOVERED 2026-10-13 → `vendor/rag-api/`, `vendor/rag-worker/`**
  (source extracted from the deployed image; `Dockerfile.irlcoop` reconstructed from its layer
  history). Originally: **no build context existed anywhere in the tree.** No
  Dockerfile, no patch, no build script. The `-1024` overlays
  (`infra/build/images/rag-embed/*/Dockerfile`) sit on an `0.1.0` base that this repo cannot
  produce. The images carry **no provenance labels**, so their origin is not recoverable from
  the artifact either.

## 4. The exposure, stated precisely

1. **Two images are irreproducible, and images are not in the backup.** `docs/BACKUP.md` tier 3
   deliberately excludes images because they are supposed to be rebuildable. For these two
   that assumption is false — so the assumption, not the image, is the hole.
2. **B's five are fragile rather than safe.** A deleted tag, a force-push, or a repo removal
   upstream breaks the build permanently, and the patch would no longer apply cleanly.
3. **The patch files themselves are already protected** — they are in the repo, so the 0.2
   off-host backup covers them. What is unprotected is the *upstream tree they apply to*.

## 5. The recovery discovery — nothing is lost yet

**The deployed image contains the patched source.** Verified 2026-10-13:

```
docker create --name p irlcoop/rag-api:0.1.0 && docker cp p:/app /tmp/probe
→ 2.1 MB recovered, 153 .py files, including pyproject.toml, langgraph.json,
  agent.py, alembic/, src/app/core/settings.py, src/app/services/retrieval_assembler.py
```

So the "lost" build context for the hard cases is **recoverable from the image** — it is a
LangGraph-based RAG service (`langgraph.json`, `langgraph_auth.py`, `agent.py`, `src/app/…`),
and its size is tiny (2.1 MB of source; the 18.5 GB in `rag-worker` is Python deps and model
weights, which are re-downloadable and must be excluded from any vendor tree).

**The window is "while the images exist".** Extraction is the first step of the fix, not a
substitute for it.

## 6. The path: fork the source into the monorepo

### 6.1 Recovery first (C images, days)
1. `docker create` + `docker cp <image>:/app` into `vendor/<app>/` — the patched source, as
   deployed.
2. Diff against the pristine upstream at the same version to separate *their* code from *our*
   patch, so the vendor tree stays legible (our change as one commit on top).
3. Record the base image and its digest; write `vendor/<app>/Dockerfile.irlcoop` (FROM the
   base, COPY the source) so the build is a single `docker build vendor/<app>`.
4. Swap `build.sh` to build from `vendor/`, with the network path kept as a documented
   fallback.

### 6.2 Vendoring layout and size control
```
vendor/<app>/            upstream tree at the pinned SHA, squashed to ONE commit
  └─ Dockerfile.irlcoop  FROM <pinned base> + COPY . + build steps
infra/build/images/<app>/build.sh        →  docker build vendor/<app>
infra/build/images/<app>/*.patch         kept: the human-readable record of our change
```
- **One squashed commit**, no upstream history (history is what makes forks huge).
- **Exclude** build outputs, fixtures, tests, and anything re-downloadable (model weights
  above all — `rag-worker` would otherwise add ~18 GB for zero recovery value).
- **`git-lfs`** for any single blob over ~10 MB (GitHub hard-rejects >100 MB).
- Expected cost, honestly: Postiz, NocoDB, Formbricks, Hi.Events, LiteFarm and Webstudio are
  large codebases; a full vendor of all six is **hundreds of MB to a few GB** in the repo. That
  is the price of not depending on someone else's git host, and it is a decision (§7).

### 6.3 NocoDB, specifically
The fork already exists and already builds reproducibly (`Dockerfile.irlcoop`, pnpm 9 pinned —
see the `nocodb-custom-build` skill). Two things remain:
- **vendor the fork** into `vendor/nocodb/` (mechanical: one squashed commit of branch
  `irlcoop`), which retires the outside-the-monorepo fork;
- **deal with the two prebuilt chunks.** They are minified build output of a *newer* nc-gui
  than the fork's source, which is why they were copied rather than built. The correct fix is
  to vendor the nc-gui source at the matching version and re-express the two changes as source
  patches (a 36-byte `loadProjects("workspace", x)` addition; deleting one `chatwootSDK.run`
  statement). Until that is done they must be recorded as **binary artifacts,
  unreproducible** — not quietly counted as buildable.

### 6.4 Provenance enforcement (so this cannot rot again)
- A **manifest** (`infra/build/images/manifest.yaml`): for every deployed `irlcoop/*` tag —
  upstream URL + SHA, patch files, base image + digest, build script.
- A **check** in `infra/scripts/build-images.sh` (or a `make verify-images`): every deployed
  tag resolves to a recipe, and no `vendor/` build reaches the network. A missing recipe fails
  loudly instead of being discovered in an emergency.

### 6.5 Licensing
These are AGPL/GPL codebases (NocoDB, Formbricks, Hi.Events, Postiz, Webstudio). Vendoring
their source into our repo **strengthens** the compliance posture — the obligation is source
availability to the people using the service, and a repo we control is a better answer than a
third-party fork. This is the same gate as `docs/design/marketplace-template-strategy.md`.

## 7. Decisions for the owner

| # | Question | Recommendation |
|---|---|---|
| 1 | Recover + vendor **C** now (2 images, small source)? | **DONE 2026-10-13** — `vendor/rag-api/` (2.2 MB, 153 `.py`) and `vendor/rag-worker/` (468 KB, 27 `.py`) recovered from the images. NocoDB remains: the fork is public and reachable (`rbpollock/nocodb` @ `a9097a26`), its tree measures **157 MB without history** |
| 2 | Vendor **B** (5 images) as well, or keep clone-at-pinned-SHA? | Vendor the **small** ones; for the large codebases weigh repo size against the upstream-disappearance risk |
| 3 | Vendored subtree or git submodule? | **Subtree.** A submodule keeps the dependency on someone else's host, which is the externality being removed |
| 4 | Where did `rag-api` / `rag-worker` come from? | Needs the owner's memory — the images carry no provenance. The source is extractable either way |