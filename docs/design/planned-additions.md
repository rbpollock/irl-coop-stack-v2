# Planned open-source additions

Apps and services that are not yet in the declared stack but are being evaluated for integration. Each entry includes the rationale, the intended pillar, and the open questions that must resolve before it becomes a declaration.

---

## ArtCraft — the open-source Creative Cloud

[ArtCraft](https://getartcraft.com) is a family of clean-room creative applications written in Rust, intended as free alternatives to Adobe Creative Cloud. As of October 2026 the suite is early alpha — functional for basic workflows, but not yet production-complete.

| ArtCraft app | Replaces | Status | Notes |
|---|---|---|---|
| **PhotoCraft** | Adobe Photoshop | alpha | Layers, masks, adjustment layers, brushes, PSD read/write |
| **VectorCraft** | Adobe Illustrator | alpha | Vector illustration, pure Rust |
| **FilmCraft** | Adobe Premiere Pro | alpha | Video editing, rebuilt from scratch |
| **LightCraft** | Adobe Lightroom | alpha | Photo library and raw developer |
| **PdfCraft** | Adobe Acrobat | alpha | PDF workbench |
| *(additional Craft apps)* | After Effects, InDesign, etc. | announced | Not yet downloadable |

### Why it is interesting

- **Rust-native** — memory-safe, fast, small distributable binaries
- **MIT / Apache-2.0** — no license friction for cooperative use
- **Offline-first** — no cloud account or Creative Cloud subscription required
- **PSD compatibility** — PhotoCraft reads and writes real PSD files, easing migration

### Why it is not declared yet

The suite is **early alpha**. The Digital Trends evaluation (October 2026) confirmed the apps run and the core workflows are recognizable, but stability, performance on large documents, and plugin ecosystems are still immature. The plan is to declare individual Craft apps as they reach beta, starting with PhotoCraft and PdfCraft because photo editing + PDF handling are the most common needs across groups.

### Open questions

1. **GPU acceleration** — does the Rust rendering stack leverage hardware compositing, or is it CPU-bound for large canvases?
2. **File-format round-trip fidelity** — can a PSD edited in PhotoCraft round-trip through GIMP / Krita without layer corruption?
3. **Group-scoped asset libraries** — ArtCraft is single-user desktop software. How do group-shared asset libraries (brushes, templates, photo pools) integrate with MinIO / cooperative file storage?
4. **Deployment model** — native desktop apps do not fit the existing Docker/Traefik stack. Is the integration boundary a download portal, a remote-desktop session, or a WASM build?

---

## Booking & rental marketplace

A cooperative needs a way to list, book, and pay for shared resources — lodging, tools, vehicles, event spaces — without handing the transaction layer to a platform like Airbnb or Vrbo.

### Candidate: Couchers.org

[Couchers.org](https://couchers.org) is an open-source, non-profit hospitality network. Unlike commercial clones, it is built around community governance and has no booking fees.

| Aspect | Detail |
|---|---|
| **License** | MIT (frontend), various OSS (backend) |
| **Stack** | Python / Django backend, React frontend, PostgreSQL |
| **Self-hostable** | Yes — the codebase is open, though the project is primarily run as a hosted service |
| **Cooperative fit** | High — non-profit, community-governed, fee-free |

### Candidate: Burrow

[Burrow](https://github.com/agriya/burrow) (also known as ReserveLogic) is an open-source rental marketplace engine. It is more of an "Airbnb clone" in the traditional sense — property listings, calendars, payments, reviews.

| Aspect | Detail |
|---|---|
| **License** | AGPL / commercial dual license |
| **Stack** | PHP / Laravel-like, MySQL |
| **Self-hostable** | Yes — designed for self-hosted deployment |
| **Cooperative fit** | Medium — the license is copyleft, but the project is less active and the UI is dated |

### Why neither is declared yet

- **Couchers.org** is hospitality-focused (traveler-host matching) rather than generic resource booking. Adapting it for tool lending, event spaces, or vehicle sharing requires significant fork work.
- **Burrow** is commercially oriented and the codebase has not seen active maintenance recently.
- The coop may need a **custom booking layer** on top of ERPNext or Plane rather than a dedicated marketplace app.

### Open questions

1. **Which model fits the coop** — peer-to-peer lodging (Couchers), commercial rental (Burrow), or resource-reservation (custom)?
2. **Payment integration** — does the booking platform talk to the Safe treasury, or does it use Stripe/card rails with later treasury reconcile?
3. **Calendar federation** — can a resource show availability across Matrix, Element Call, and the booking UI without double-booking?
4. **Identity and trust** — are bookings gated by ZK-membership proofs, or by group affiliation alone?

---

## How to move an entry from "planned" to "declared"

1. Open an issue in `irl-coop-stack-v2` titled `evaluate: <app-name>`
2. Answer the open questions above with evidence (spike container, docs read, pilot run)
3. Write the app YAML in `infra/instances/dev/apps/<app>.yaml`
4. Add the nav entry and proxy route
5. Update `stack-catalog.md` and `README.md`
6. Merge
