# Restreamer integration

Status: **design** (app declaration, proxy route, and SSO gate ready; encoder presets and per-group stream isolation are the next slice).

[Restreamer](https://github.com/datarhei/restreamer) is a self-hosted streaming server that ingests video via RTMP / SRT and publishes it simultaneously to multiple destinations (YouTube, Twitch, custom HLS players) while also serving its own HLS and WebRTC output. It replaces the need for cloud multistreaming services and gives the coop full custody of its broadcast pipeline.

## Why it belongs in the stack

The stack already has two pieces of live-media infrastructure:

- **MediaMTX** — a protocol router: RTMP/RTSP/SRT in, HLS/WebRTC/RTSP out. It is stateless, has no UI, and is perfect for *consuming* a stream (e.g. a security camera feeding a dashboard tile).
- **LiveKit** — a WebRTC SFU for real-time *calls* and interactive video (Matrix/Element Call).

What is missing is a *broadcaster-facing* layer: a place where a group member opens a web UI, pastes a stream key from OBS, and decides which platforms (or which internal players) receive the feed. That is exactly Restreamer.

## How it fits

```text
OBS / camera / phone
        |
        v
[Restreamer]  ----->  YouTube / Twitch / etc.   (external restream)
        |  |
        |  +----->  HLS player on group home        (internal viewing)
        |  +----->  MediaMTX path / backup ingest    (optional bridge)
        |
   Web UI at restreamer.${DOMAIN}
   protected by coop OIDC gate
```

## App declaration (proposed)

`infra/instances/dev/apps/restreamer.yaml`

```yaml
# Restreamer — self-hosted video ingestion, encoding, and multi-platform restreaming.
# The UI lets group members configure streams without touching config files.
# RTMP ingest on 1935 (router port-forward, not edge route).
name: restreamer
enabled: true
pillar: communication
type: image
image: datarhei/restreamer:vaapi-latest
ports:
  - "1945:8080"   # Web UI — edge-routed via Traefik (restreamer.${DOMAIN})
  - "1936:1935"   # RTMP ingest — router forwards like MediaMTX
  - "6000:6000/udp" # SRT ingest (optional)
volumes:
  - /opt/app/communication/data/restreamer:/restreamer/db
  - /opt/app/communication/etc/restreamer:/restreamer/config:ro
restart: unless-stopped
proxy:
  hostname: restreamer.${DOMAIN}
  port: 8080
  description: Restreamer broadcast ingest and restream UI
nav:
  label: Broadcast
  href: /apps/restreamer
  icon: Radio
  section: Coop
```

## Open questions / next slices

1. **Hardware acceleration** — the `vaapi-latest` tag uses Intel/AMD VAAPI for encoding. Do the host nodes have iGPU? Is a CPU-only (`latest`) fallback needed?
2. **Per-group stream isolation** — Restreamer is single-tenant out of the box. Multiple groups need either:
   - One Restreamer instance per group (heavy), or
   - A shared instance with coop-managed path-prefix routing and JWT-scoped stream configs.
3. **Integration with MediaMTX** — should Restreamer push *into* MediaMTX as an additional output path, so internal viewers use the same `stream.${DOMAIN}` endpoint regardless of source?
4. **Recording / archival** — Restreamer can write to disk. Should recordings land in MinIO (`streams` bucket) automatically?
5. **Metrics and event bus** — ingest `stream_start`, `viewer_count`, `platform_disconnect` events into the coop Redis bus for dashboard activity feeds.
