# irl.coop Stack Catalog

Complete inventory of the apps declared in `infra/instances/dev/instance.yaml`.

- **Open-source** apps show their project logo inside a colored badge.
- **Custom-built** components use the irl.coop placeholder badge.

**42 elements total** — 31 open-source, 11 custom-built.

## Pillars

- [Proxy](#proxy)
- [Authentication](#authentication)
- [Cache](#cache)
- [Storage](#storage)
- [Communication](#communication)
- [Maps](#maps)
- [Workflow](#workflow)

### Proxy

| | App | What it does | |
|:---:|:---|:---|:---:|
| <img src="logos/badges/traefik.svg" width="28" alt="traefik"> | **[Traefik](https://traefik.io)** | Edge router and reverse proxy that handles all ingress. | OSS |

### Authentication

| | App | What it does | |
|:---:|:---|:---|:---:|
| <img src="logos/placeholder.svg" width="28" alt="coop-api"> | **coop-api** | irl.coop auth bridge, federation gateway, and event bus. | Custom |
| <img src="logos/badges/keycloak.svg" width="28" alt="keycloak"> | **[Keycloak](https://www.keycloak.org)** | Identity broker and OIDC provider with coop federation support. | OSS |

### Cache

| | App | What it does | |
|:---:|:---|:---|:---:|
| <img src="logos/badges/irl-redis.svg" width="28" alt="irl-redis"> | **[irl-redis](https://redis.io)** | Shared caching layer, session store, and queue backend. | OSS |

### Storage

| | App | What it does | |
|:---:|:---|:---|:---:|
| <img src="logos/badges/citus.svg" width="28" alt="citus"> | **[Citus](https://www.citusdata.com)** | Distributed PostgreSQL (Citus) — the core data plane with RLS. | OSS |
| <img src="logos/badges/nocodb.svg" width="28" alt="nocodb"> | **[NocoDB](https://nocodb.com)** | Spreadsheet/database UI over Postgres with SSO gate. | OSS |

### Communication

| | App | What it does | |
|:---:|:---|:---|:---:|
| <img src="logos/badges/cinny.svg" width="28" alt="cinny"> | **[Cinny](https://cinny.in)** | Matrix web client — lightweight alternative to Element. | OSS |
| <img src="logos/badges/coturn.svg" width="28" alt="coturn"> | **[Coturn](https://github.com/coturn/coturn)** | TURN/STUN server for NAT traversal in WebRTC calls. | OSS |
| <img src="logos/badges/element-call.svg" width="28" alt="element-call"> | **[Element Call](https://github.com/vector-im/element-call)** | Group video calling via Matrix/WebRTC. | OSS |
| <img src="logos/badges/element-web.svg" width="28" alt="element-web"> | **[Element Web](https://element.io)** | Primary Matrix web client. | OSS |
| <img src="logos/badges/freeswitch.svg" width="28" alt="freeswitch"> | **[FreeSWITCH](https://freeswitch.org)** | SIP/VoIP softswitch for telephony routing. | OSS |
| <img src="logos/badges/fusionpbx.svg" width="28" alt="fusionpbx"> | **[FusionPBX](https://www.fusionpbx.com)** | Web GUI and PBX management layer on top of FreeSWITCH. | OSS |
| <img src="logos/badges/livekit.svg" width="28" alt="livekit"> | **[Livekit](https://livekit.io)** | WebRTC SFU for real-time audio, video, and data. | OSS |
| <img src="logos/badges/lk-jwt.svg" width="28" alt="lk-jwt"> | **[lk-jwt](https://github.com/element-hq/lk-jwt-service)** | LiveKit JWT token issuer for Matrix/Element Call. | OSS |
| <img src="logos/badges/matrix.svg" width="28" alt="matrix"> | **[Matrix](https://matrix.org)** | Synapse Matrix homeserver (custom image with S3 media store). | OSS |
| <img src="logos/badges/mediamtx.svg" width="28" alt="mediamtx"> | **[Mediamtx](https://github.com/bluenviron/mediamtx)** | RTSP/RTMP/SRT media server. | OSS |
| <img src="logos/badges/roundcube.svg" width="28" alt="roundcube"> | **[Roundcube](https://roundcube.net)** | Webmail client with OIDC integration. | OSS |
| <img src="logos/badges/stalwart.svg" width="28" alt="stalwart"> | **[Stalwart](https://stalw.art)** | Modern mail server (IMAP/SMTP) with OIDC and sieve support. | OSS |
| <img src="logos/badges/restreamer.svg" width="28" alt="restreamer"> | **[Restreamer](https://github.com/datarhei/restreamer)** | Self-hosted streaming ingest, encoding, and multi-platform restreaming. | OSS |

### Maps

| | App | What it does | |
|:---:|:---|:---|:---:|
| <img src="logos/placeholder.svg" width="28" alt="maps"> | **Maps** | Custom map tile server and geo frontend (nginx-based). | Custom |

### Workflow

| | App | What it does | |
|:---:|:---|:---|:---:|
| <img src="logos/badges/erpnext.svg" width="28" alt="erpnext"> | **[ERPNext](https://erpnext.com)** | ERP (accounting, inventory, CRM) for cooperative operations. | OSS |
| <img src="logos/badges/formbricks.svg" width="28" alt="formbricks"> | **[Formbricks](https://formbricks.com)** | Open-source form builder and survey platform with SSO gate. | OSS |
| <img src="logos/badges/hievents.svg" width="28" alt="hievents"> | **[Hi.Events](https://github.com/HiEventsDev/hi.events)** | Event ticketing and registration (custom Gate SSO fork). | OSS |
| <img src="logos/badges/litefarm.svg" width="28" alt="litefarm"> | **[LiteFarm](https://litefarm.org)** | Farm management records and planning tool. | OSS |
| <img src="logos/placeholder.svg" width="28" alt="llm-inference"> | **LLM Inference** | Local LLM inference endpoint (custom wrapper). | Custom |
| <img src="logos/badges/onlyoffice.svg" width="28" alt="onlyoffice"> | **[OnlyOffice](https://www.onlyoffice.com)** | Collaborative document editing server (Docx/Xlsx/Pptx). | OSS |
| <img src="logos/placeholder.svg" width="28" alt="peer_xyz_payments"> | **peer_xyz_payments** | Custom payment-rail wrapper and webhook receiver. | Custom |
| <img src="logos/badges/plane.svg" width="28" alt="plane"> | **[Plane](https://plane.so)** | Open-source project management (custom gate SSO fork). | OSS |
| <img src="logos/placeholder.svg" width="28" alt="plane-mcp"> | **plane-mcp** | Model Context Protocol (MCP) bridge for Plane. | Custom |
| <img src="logos/badges/postiz.svg" width="28" alt="postiz"> | **[Postiz](https://postiz.com)** | Social media scheduling and publishing platform. | OSS |
| <img src="logos/badges/rag.svg" width="28" alt="rag"> | **[RAG](https://www.postgresql.org)** | Vector database (pgvector) backing the RAG pipeline. | OSS |
| <img src="logos/placeholder.svg" width="28" alt="rag-api"> | **rag-api** | RAG query and retrieval API. | Custom |
| <img src="logos/placeholder.svg" width="28" alt="rag-inference"> | **rag-inference** | Embedding + reranking inference service. | Custom |
| <img src="logos/placeholder.svg" width="28" alt="rag-migrate"> | **rag-migrate** | RAG database migration and schema initializer. | Custom |
| <img src="logos/placeholder.svg" width="28" alt="rag-worker"> | **rag-worker** | RAG indexing and document-processing worker. | Custom |
| <img src="logos/badges/temporal.svg" width="28" alt="temporal"> | **[Temporal](https://temporal.io)** | Workflow orchestration and durable execution engine. | OSS |
| <img src="logos/badges/temporal-ui.svg" width="28" alt="temporal-ui"> | **[temporal-ui](https://temporal.io)** | Web UI for inspecting Temporal workflow runs and history. | OSS |
| <img src="logos/placeholder.svg" width="28" alt="treasury-relayer"> | **treasury-relayer** | Safe treasury relayer for cross-chain operations. | Custom |
| <img src="logos/badges/webstudio.svg" width="28" alt="webstudio"> | **[Webstudio](https://webstudio.is)** | Visual, collaborative website builder. | OSS |
| <img src="logos/badges/wordpress.svg" width="28" alt="wordpress"> | **[WordPress](https://wordpress.org)** | CMS and blogging platform (custom container with WP-CLI). | OSS |
| <img src="logos/placeholder.svg" width="28" alt="zk-proving"> | **zk-proving** | Zero-knowledge proof generation and verification service. | Custom |

---

*Generated from the declarative source-of-truth in `infra/instances/dev/`.*
Badge icons are derived from [Simple Icons](https://simpleicons.org/) where available, or rendered as initials for projects without an icon in that set.

---

## Planned additions

Apps being evaluated but not yet declared: [`planned-additions.md`](planned-additions.md)
