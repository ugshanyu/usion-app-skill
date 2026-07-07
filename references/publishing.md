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

## Path C — Programmatic registration with an API token (agents / automation)

When an AI agent or script registers and manages services without a human in
the loop, authenticate with a **personal API token** instead of a seed script.

1. The owner mints a token in the app: **Service Creator → Agent API Access →
   Create API token**. The raw token (`usion_sk_…`) is shown **once** — copy it.
   Tokens are long-lived, revocable, and listed/revoked from the same screen.
2. The agent calls the registry with `Authorization: Bearer usion_sk_…`. The
   token acts as the owning user but is **scoped to service management only** —
   it is rejected on wallet/chat/etc., so it's safe to hand to an agent.

```
POST   {API_URL}/registry/services/register          # register (app/game/bot/skill)
GET    {API_URL}/registry/services/my                 # list your services
PUT    {API_URL}/registry/services/my/{id}            # update
PATCH  {API_URL}/registry/services/my/{id}/publish    # publish / unpublish
DELETE {API_URL}/registry/services/my/{id}            # delete
POST   {API_URL}/registry/services/my/{id}/notify-secret   # mint/rotate notify secret
```

Register body matches the Service Creator form: `{name, description, service_type,
iframe_url, cost, tags, is_published, realtime?, max_players?, ...}`. A `bot`
service also returns `bot_credentials` (token + webhook secret) once.

Token management endpoints (`POST/GET/DELETE /registry/api-tokens`) require a
real login session — an API token cannot mint more API tokens (no escalation).

E2E test: `cd backend && python -m scripts.test_api_tokens`.

## Server-triggered notifications (your backend → a Usion user)

When a job finishes while the app is closed (e.g. a video render), your own
backend notifies the user via the signed REST endpoint — the in-app
`Usion.notify` only works while the app is open.

```
POST {API_URL}/services/{service_id}/notify
Header  X-Usion-Signature: <hex HMAC-SHA256 of the raw body>
Body    {"user_id": "...", "title": "...", "body": "...", "path": "/optional/in-app/path"}
```

- **Auth:** HMAC-SHA256 over the exact raw request body, keyed by the service's
  `realtime.signing.shared_secret` (≥ 16 chars). `403` if no secret is
  configured, `401` on signature mismatch.
- **Where the secret comes from** — it is **revealed exactly once** and is
  write-only thereafter (every read excludes it), so store it in your backend's
  env (e.g. `USION_NOTIFY_SECRET`) when you get it. Three ways to obtain one:
  - **Creator path** (`usk_live_…` key): auto-minted when you register via
    `POST /services` (returned once as `signing_secret`); the AI Creator publish
    flow mints one too. Lost it? Rotate (owner-only):
    `POST /services/{id}/signing-secret/rotate` → fresh `signing_secret`, old one
    dies immediately.
  - **Mobile-user path** (`usion_sk_…` token, Service Creator UI): mint/rotate via
    `POST /registry/services/my/{id}/notify-secret` (returns the secret once; see
    Path C).
  - **Seed script** (`KLING_NOTIFY_SECRET` → `seed_*.py`) for first-party
    services that set it explicitly.
- **Scope/limits:** identical to `Usion.notify` — only that service's user,
  ≤ 20/hour per user, title/body/path sanitized + capped, muted users dropped.
- Online users get an in-app banner; offline users get an OS push that reopens
  the app at `path`. Response: `{"success": true, "delivered": "banner"|"push"|"muted"}`.

Node example:

```javascript
const body = JSON.stringify({ user_id, title: 'Render complete', body: 'Tap to view', path: `/render/${id}` });
const sig = crypto.createHmac('sha256', SHARED_SECRET).update(body).digest('hex');
await fetch(`${API_URL}/services/${SERVICE_ID}/notify`, {
  method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Usion-Signature': sig }, body });
```

E2E test: `cd backend && python -m scripts.test_notifications`.

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
| **Tilt Royale** (direct-mode reference) | https://tilt-royale-production.up.railway.app | https://github.com/ugshanyu/tilt-royale · seed `backend/scripts/seed_tilt_royale.py` — 2–4p server-authoritative tilt battle royale on Railway Singapore; the most complete example of the SDK netcode helpers (`createPredictor` + `createInterpolation`) + server-side lag compensation, with a shared pure-physics module so client prediction stays bit-identical to the server sim. Read its README as a direct-mode tutorial. |
| **Tank Arena** (direct-mode, binary protocol) | https://tank-production-5873.up.railway.app | https://github.com/ugshanyu/tank · seed `backend/scripts/seed_tank.py` — 2–8p tilt-to-drive / touch-to-shoot arena. Direct-mode reference that does NOT use the SDK's JSON realtime channel: it mints the access token via `Usion.game._fetchDirectAccess` then opens its OWN **binary** WebSocket (11-byte inputs, quantized snapshots) to the Railway server, which validates the RS256 token against the platform JWKS (`server/auth.js`). Shared deterministic sim → client prediction + reconciliation + entity interpolation. The Railway server also serves the static client (one host for iframe + WS). Use this pattern when you want maximum wire efficiency and your own transport instead of `Usion.game.realtime`. |
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
