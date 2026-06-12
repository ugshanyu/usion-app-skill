# Publishing a Usion app + live deployed references

## Path A — Static bundle (AI-Creator pipeline)

Bundle = self-contained `index.html` (CSS/JS inlined, no CDNs, no build step).
Do NOT include the SDK script tag — `host.py` injects
`<script src="https://usions.com/usion-sdk.js"></script>` into `<head>` at
deploy time (`backend/services/miniapp_builder/host.py`).

Hosting (S3, bucket `mongolgpt-messenger`, ap-southeast-1; served via the
custom domain when `AWS_S3_CUSTOM_DOMAIN` is set; `CacheControl: no-cache`):

- Preview: `miniapps/preview/{project_id}/{session_id}/index.html`
- Release: `miniapps/apps/{project_id}/v{version}/index.html`

Publish flow (`orchestrator.publish_app`):
1. Tier-1 moderation/quality gate (fails → 422 with issues).
2. `_detect_kind` reads the BUILT code: `multiplayer = true` iff it contains
   `Usion.game.join` / `realtime` / `action` / `connect` /
   `.onPlayerJoined` / `.onRealtime`; `game = Usion.game.*` present. Tags and
   realtime config come from what the code actually does, not what it claims.
3. Service upserted in the registry: tags `[game|app, "ai-generated",
   "iframe"]` (+ `"multiplayer"`), `iframe_url` = live URL. Multiplayer games
   get `realtime: {connection_mode: "platform", connection_transport:
   "websocket"}` → rooms, matchmaking, and `game_invite` chat flow work
   automatically.
4. Each publish bumps `current_version` and writes a `MiniAppVersion` doc.
   Visibility: public (default, searchable) or private.

Quality flags that trigger auto-repair / rejection: `mp_missing_join`,
`mp_missing_sync`, `mp_missing_peer_events`, `fictional_sdk_call`, `no_script`.
Avoid all five by construction.

## Path B — Hand-built microservice

1. Create `microservices/<name>/` (Next.js is the house pattern; see existing
   services). Load the SDK yourself in the page:
   `<script src="https://usions.com/usion-sdk.js"></script>`
   (local dev: `http://localhost:3100/usion-sdk.js` from the shared design
   system service).
2. Deploy: **Vercel** for client-only apps; **Railway** when the game needs its
   own server (direct mode). Note from project memory: Vercel deploys from this
   monorepo can get stuck — rsync the service to /tmp and deploy from a non-git
   dir if needed.
3. Register the service in the registry with a seed script — copy the pattern
   in `backend/scripts/seed_example_games.py` (sets name, description,
   `iframe_url`, `service_type`, tags, `game_config`/`realtime`). ⚠️ Seed
   scripts run against the PRODUCTION MongoDB (see CLAUDE.md) — read before
   writing, prefix test entities.
4. Local dev ports are assigned in CLAUDE.md's Service Ports table; add yours.

## Releasing an SDK change (only if the app needs a new SDK API)

Follow CLAUDE.md "How to release an SDK change" exactly: edit
`packages/sdk/src/modules/*.js` (never the build artifacts), update
`packages/sdk/types/index.d.ts`, `npm run build:copy` + `npm test`, bump
version, commit source + artifacts together. Web deploy ships the injected
bundle to all iframes; npm publish is automated by
`.github/workflows/publish-sdk.yml`.

## Live deployed exemplar apps (verified in seed scripts / repo)

Official reference games (seeded by `backend/scripts/seed_example_games.py`):

| App | Live URL | Git repo | What it demonstrates |
|-----|----------|----------|----------------------|
| Space Invaders Duel (turn-based reference) | https://usion-example-turnbased.vercel.app | https://github.com/ugshanyu/usion-example-turnbased | `action()`/`onAction` turn-based pattern |
| Tag Arena (real-time reference) | https://usion-example-realtime.vercel.app | https://github.com/ugshanyu/usion-example-realtime | host-authoritative realtime loop; direct server at https://tag-arena-server-production.up.railway.app |

Other production deployments:

| App | Live URL | Source |
|-----|----------|--------|
| XO 8×8 | https://usion-xo-platform.vercel.app | https://github.com/ugshanyu/usion-xo-platform · seed `backend/scripts/seed_xo8x8.py` |
| Pong (WebRTC) | https://pong-webrtc-production.up.railway.app | https://github.com/ugshanyu/usion-pong-webrtc · `microservices/pong/` — DataChannel + WS fallback |
| Space Craft v2 | https://space-craft-v2-production.up.railway.app | https://github.com/ugshanyu/space-craft-v2 — 4-player server-authoritative |
| Contra P2P | https://contra-p2p-production.up.railway.app | https://github.com/ugshanyu/usion-contra-p2p — browser-to-browser WebRTC |
| Voiceify TTS | https://voiceify-tts.vercel.app | `microservices/voiceify-tts/` (monorepo) |
| Kling/MongolGPT Studio | https://kling-studio.vercel.app | https://github.com/ugshanyu/mongolgpt-studio (private) · `microservices/kling-studio/` |
| Video Editor | https://video-editor-bay.vercel.app | `microservices/video-editor/` |
| Random Chat | https://random-chat-production-31c3.up.railway.app | `microservices/random-chat/` |
| UsionFlow mini-app | https://app.mongolgpt.mn/miniapp | `backend/scripts/seed_usionflow_miniapp.py` |

SDK + design system:

- SDK bundle (injected/loaded by every app): https://usions.com/usion-sdk.js
- Design tokens: https://usions.com/usion-design-system.css

In-repo source exemplars: `microservices/tic-tac-toe/app/page.tsx`
(platform-mode lifecycle), `microservices/pong/` (direct mode + WebRTC),
`microservices/block-stack/server.js` (`RoomRuntime` authoritative loop),
`microservices/tilt-arena/` (device-orientation input, 10 players).
