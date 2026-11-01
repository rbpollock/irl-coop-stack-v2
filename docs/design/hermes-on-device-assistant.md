# Hermes On-Device Assistant — native Android shell (design)

Status: scoped, not built · Oct 2026 · Companion to `android-mini-services-client.md`
(the phone-as-node doc — same mesh, same sovereign principles) and the Hermes
WebUI bring-up described in this repo's notes.

## 0. The problem

Robbie's Hermes WebUI (tailnet, loopback-only, OIDC-gated via the irl-coop
realm) already runs as an installable PWA with browser notifications and server
TTS (Edge TTS). Two gaps remain that a PWA cannot close:

1. **Assistant role** — the long-press power / long-press home trigger that
   summons the phone's *default assistant*. Android grants this only to a
   native package holding `ROLE_ASSISTANT` (the assist intent with
   `android:trigger`). No web app — Chrome or PWA — can claim it.
2. **Instant speaker autoplay** — play the response out loud the moment it
   lands, with a wake lock, while the app is backgrounded. A backgrounded
   browser cannot reliably autoplay the phone's speaker.

So the full "on-device assistant" behaviour needs a small native Android app
that wraps/integrates Hermes. This document scopes that app.

## 1. What the app must do

| capability | behaviour |
|---|---|
| Assistant role | Declare the assist intent, be selectable as the system assistant from a long-press power/home. |
| Authenticate as Robbie | OIDC authccode + PKCE against `auth.irl.coop/realms/irl-coop`, client `hermes-webui` (or a dedicated `hermes-android` client), gate `email=robbie@irl.coop`. |
| Listen / speak | Reuse the Hermes HTTP API + WebUI TTS. Mic → STT (Edge/Web Speech/app-side), reply → TTS audio. |
| Notification + autoplay | A foreground service keeps the agent session alive, posts a system notification when a reply completes, and can autoplay the Edge-TTS audio (wake lock) or hand off to a media/player notification. |
| Reconnect path | Tailscale mesh so the phone reaches the loopback-only Hermes host without a public IP (mirrors the mini-services-client mesh). |

## 2. Sizing — honest

This is a **real native project**, not a "wrap the PWA" step: Kotlin + Android
app scaffolding, the assistant intent + `ROLE_ASSISTANT` handling, a foreground
service that budgets battery against a "service node" that stays alive, OIDC
token refresh, and TTS-audio handoff. Rough but useful bounds:

- minimal MV build: an assistant-registered shell that opens the PWA/URL and
  posts a notification → days, using an embedded WebView plus a service.
- autoplay + wake-lock + district on the live Huawei: 1–2 weeks focused.
- needs a dev signing key and an APK install on the S22 (sideload, since it
  won't be on Play for now — it's a personal/coop tool, private distribution).

## 2.5 Prior art / decision to reuse

- PWA gives notifications + voice *in-tab and backgrounded-enough* already.
- The Android Mini-Services client (android-mini-notes.md) and this app share
  Tailscale, OIDC, and the "phone is a node" frame; if that project proceeds,
  the assistant is a natural screen/module inside it rather than a separate app.
  **Recommend: build the assistant as a screen/service of the mini-services
  client, not a standalone app.**

## 3. Next-determined tasks

1. Confirm the dev target phone is on the tailnet (S22, `roberts-s22` — seen in
   `tailscale status`), Tailscale Android installed.
2. Decide: standalone assistant wrapper vs. module of the android-mini-services
   client. (Recommendation above.)
3. If standalone: scaffold a Kotlin project, add the assist intent, WebView +
   OIDC PKCE, foreground service for the live notification + autoplay.
4. Add a PWA-serving note: when MagicDNS flips the host to `hermes.…`, PWA
   origin changes and the Keycloak redirect must be updated (pre-registered).

Status: scoped, awaiting the "go".