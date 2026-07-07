---
name: usion-app
description: >-
  How to build, test, and publish a mini-app or game for the Usion platform
  using the Usion SDK (@usions/sdk). Use this skill whenever the user wants to
  create, modify, or ship anything that runs inside Usion — a mini-app, a game
  (single-player or multiplayer), an iframe service, a chat widget, or a
  microservice — or asks what the Usion SDK can do (Usion.game, Usion.wallet,
  Usion.cloud, Usion.notify, lobby, matchmaking, leaderboard, netcode). Also use it when
  registering a service in the Usion registry or deploying to S3/Vercel/Railway
  for Usion, even if the user doesn't say "SDK" explicitly.
---

# Building an app for Usion

Usion mini-apps are static web apps that run inside an iframe (WebView on mobile)
in the Usion chat app. The platform injects identity, wallet, theme, storage,
and a full multiplayer transport — your app talks to all of it through one
global object: `window.Usion`.

## Reference files (read on demand)

| File | Read it when |
|------|--------------|
| [references/sdk-reference.md](references/sdk-reference.md) | You need the exact API surface — any `Usion.*` method, its signature, quotas, or callback shape |
| [references/multiplayer.md](references/multiplayer.md) | The app is a multiplayer game — room lifecycle, host-authoritative pattern, netcode helpers |
| [references/publishing.md](references/publishing.md) | You're deploying/registering the app — hosting paths, service registry, and links to live deployed exemplar apps |
| [references/agent-api.md](references/agent-api.md) | You're an AI agent registering/managing services via the REST API with a creator API key — auth, `POST /services`, capturing the one-time signing secret, rotating it |

## Step 1 — Decide the delivery path

There are two ways an app reaches users. Pick one first; it changes everything
about structure and deploy.

**Path A — Static bundle (AI-Creator style).** One self-contained `index.html`
(CSS + JS inlined, no build step, no external CDNs). Hosted on S3 by the
platform; the platform **injects** `<script src="https://usions.com/usion-sdk.js"></script>`
into the `<head>` at deploy — do NOT include the SDK script tag yourself, just
assume `window.Usion` exists. This is the right path for most apps and games.

**Path B — Hand-built microservice.** A full project (usually Next.js) under
`microservices/<name>/`, deployed yourself (Vercel for static/SSR, Railway when
it needs its own game server), then registered in the service registry with its
public URL as `iframe_url`. Here YOU load the SDK with
`<script src="https://usions.com/usion-sdk.js"></script>` (or
`http://localhost:3100/usion-sdk.js` in local dev). Choose this when the app
needs a server of its own (direct-mode game server, webhooks, APIs).

## Step 2 — App skeleton

Every app starts the same way:

```javascript
Usion.init(function (config) {
  // config: { userId, userName, userAvatar, balance, theme: 'light'|'dark',
  //           language, roomId, playerIds, serviceId, socketUrl, ... }
  // Start your app HERE — never before init fires.
});
```

Rules that the platform's automated quality checker enforces (violations get
builds flagged/rejected):

- Use ONLY real SDK methods. **These do not exist:** `Usion.ready`,
  `Usion.user.info`, `Usion.game.emit`. Use `Usion.init(cb)`,
  `Usion.user.getId()/getName()/getAvatar()`, `Usion.game.action()/realtime()`.
- A multiplayer game MUST call `Usion.game.connect()` then
  `Usion.game.join(config.roomId)` and register `onPlayerJoined` / `onRealtime`
  (or `onAction`) handlers — register these UP FRONT, even on a `'single'`
  launch, since the host can promote a solo game to multiplayer mid-session
  (handle `Usion.game.onRoomAssigned`; see Step 4).
- Money moves only through `Usion.wallet.requestPayment(amount, reason)` —
  never invent custom payment flows.
- Do NOT build room codes, invite/share UIs, matchmaking UIs, or wager
  pickers — the platform owns those (rooms, matchmaking, `game_invite` chat
  flow). Your game receives `config.roomId` and `config.playerIds` already set.
  An in-game **waiting room / ready screen** IS allowed (optional): while
  invited players trickle into the room a game MAY show who's present with a
  ready toggle and a host-start (see the multiplayer reference). A simple duel
  should still just start the moment everyone in `config.playerIds` has joined.

Design: mobile-first, small embedded frame, Vercel-inspired minimalism
(black/white, flat, generous whitespace). Respect `Usion.getTheme()` and
`Usion.getLanguage()` — don't hardcode user-facing strings to one locale.

## Step 3 — Pick your capabilities

Quick map of what the platform offers (full signatures in the SDK reference):

- **Identity**: `Usion.user.getId/getName/getAvatar/getProfile`
- **Money**: `Usion.wallet.getBalance/hasCredits/requestPayment/onBalanceChange`
- **Device-local storage** (per user, per app): `Usion.storage.get/set/remove/clear/keys` (512 KB/value) and `Usion.fileStorage` for base64 blobs
- **Cloud KV** (server-persisted, cross-device): `Usion.cloud.get/set/remove/keys` + shared per-app bucket `Usion.cloud.shared.*` with atomic `shared.incr` — 64 KB/value, 200 keys & 1 MB/bucket, 60 ops/min
- **Multiplayer**: `Usion.game.connect/join/action/realtime` + `on*` handlers; netcode helpers (interpolation, prediction, delta snapshots, lockstep, WebRTC mesh, WebTransport)
- **Launch mode**: `Usion.getLaunchParams().mode` is `'single'` (opened from Explore / the Game hub, solo) or `'multiplayer'` (opened from a chat game invite); `Usion.game.isMultiplayer()` is the boolean. Branch your setup on it — don't infer mode from `roomId`, the host declares it. (SDK ≥ 2.18)
- **Social**: `Usion.lobby.*` (parties + codes), `Usion.matchmaking.find/cancel/onMatch`, `Usion.leaderboard.submit/top/friends/me`
- **Invite friends**: `Usion.game.invite()` opens the host's friend/group picker (recent + username search + groups, multi-select) and fills your room — tappers join THIS room and you get `onPlayerJoined`. Works even when launched solo (host makes a room, joins you as host). The host ALSO shows a top-bar **Share** button on every game (same picker) — using it promotes a solo launch into a room and fires `Usion.game.onRoomAssigned`. Don't build your own invite/Share UI. (SDK ≥ 2.20)
- **Chat integration**: `Usion.chat.sendMessage/createPersonalChat`, `Usion.bot.*` for inline bot widgets
- **Permissions**: `Usion.permissions.request(['notifications'])` shows a host modal (allow/cancel); `query`/`has` read state without prompting. Capabilities are platform-enforced — **ask before you act**. Users manage grants later in app settings. First permission: `notifications`. (SDK ≥ 2.17)
- **Notifications**: `Usion.notify.send({title, body, path?})` notifies the app's own user (in-app banner online / OS push offline); tapping reopens the app at `path` (read via `Usion.getLaunchParams().path`). **Call `Usion.permissions.request(['notifications'])` first** — without a grant, `send` returns `delivered:'blocked'` (existing/already-published apps are grandfathered). The notification's **title is always your mini-app's name** — your `title`/`body` become the message; don't repeat the app name in `title`. `setMuted`/`isMuted` for opt-out. Server-triggered: signed `POST /services/{id}/notify`
- **Results & sharing**: `Usion.saveResult`, `Usion.share`, `Usion.shareToFeed`, `Usion.download`
- **Lifecycle/UI**: `Usion.exit()`, `Usion.claimBackButton(cb)`, `Usion.setLoading`, `Usion.toggle`, theme/language getters

Backend-channel modules (lobby `lobby:*`, matchmaking `mm:*`, leaderboard
`lb:*`, cloud `kv:*`, notify `notify:*`) work both standalone and embedded automatically. Adding a
NEW event prefix requires allowlist changes in both hosts plus a backend
handler — see CLAUDE.md "Backend channel rule" before attempting.

## Step 4 — Multiplayer (if applicable)

Read [references/multiplayer.md](references/multiplayer.md). The core contract:

- The platform relays via Socket.IO; **`config.playerIds[0]` is the host** and
  the single source of truth (host-authoritative pattern).
- **Register multiplayer handlers up front.** Wire `onPlayerJoined`, `onJoined`,
  and `onAction`/`onRealtime` regardless of launch mode — even when
  `getLaunchParams().mode === 'single'`. A solo-launched game can be promoted to
  host mid-session when the user taps the host's Share button: handle
  `Usion.game.onRoomAssigned` (SDK ≥ 2.20) to flip from the solo view into the
  hosting view (the SDK has already set `roomId`/`mode` and auto-joined;
  `onJoined` fires right after). Don't gate multiplayer setup behind
  `isMultiplayer()`/`mode` at launch.
- Host steps the simulation and broadcasts state with
  `Usion.game.realtime('state', {...})`; guests send inputs with
  `Usion.game.realtime('input', {...})`; host decides the winner and announces
  `realtime('gameover', { winner_id })`.
- `action()` is sequenced + stored (turn-based moves); `realtime()` is
  fire-and-forget (per-frame state). Never trust a peer's self-reported score
  for paid outcomes — compute on the host.
- Handle `onPlayerLeft` (forfeit/win) and `onDisconnect`/`onReconnect`.

## Step 5 — Test before calling it done

- Open the app locally and verify `Usion.init` fires (the SDK no-ops gracefully
  outside the host, but state your assumptions).
- For multiplayer: test with two browser windows; use
  `Usion.game.simulateNetwork({ latencyMs, jitterMs, lossPct })` to verify it
  survives bad networks.
- Grep your own code for fictional SDK calls (`Usion.ready`, `Usion.game.emit`,
  `Usion.user.info`) — the platform's quality checker will flag them.
- Cloud KV end-to-end: `cd backend && python -m scripts.test_cloud_kv`.
- Notifications end-to-end: `cd backend && python -m scripts.test_notifications`.

## Step 6 — Publish

Read [references/publishing.md](references/publishing.md) for the exact flow.
Summary: Path A bundles deploy to S3 (`miniapps/apps/<project>/v<n>`) and
register automatically via the AI Creator publish flow; Path B microservices
deploy to Vercel/Railway and register via a seed script following
`backend/scripts/seed_example_games.py`. Capability tags (`game`,
`multiplayer`) are detected from the BUILT code — a multiplayer game that never
calls `Usion.game.join` will not get multiplayer rails.

## Working exemplars (study before writing code)

- `microservices/tic-tac-toe/app/page.tsx` — cleanest platform-mode multiplayer
  lifecycle. Live: https://usion-example-turnbased.vercel.app (turn-based
  reference) and https://usion-example-realtime.vercel.app (real-time Tag Arena).
- `microservices/pong/` — WebRTC DataChannel + WebSocket fallback, network
  simulation. Live: https://pong-webrtc-production.up.railway.app
- `microservices/block-stack/server.js` — host-authoritative `RoomRuntime`
  game loop, up to 8 players.
- `ugshanyu/tilt-royale` (standalone repo) — the most complete **direct-mode**
  reference: 2–4p server-authoritative tilt battle royale on Railway Singapore,
  60 Hz sim / 20 Hz delta snapshots, SDK `createPredictor` + `createInterpolation`
  + server-side lag compensation, shared pure-physics module. Its README is a
  direct-mode + netcode tutorial. Live: https://tilt-royale-production.up.railway.app
- `ugshanyu/tank` (standalone repo) — **direct-mode with a custom BINARY
  protocol** (not the SDK's JSON realtime channel): 2–8p tilt-to-drive /
  touch-to-shoot arena. Mints the access token via
  `Usion.game._fetchDirectAccess`, then opens its own binary WebSocket (11-byte
  inputs, quantized snapshots) to a Railway server that validates the RS256 token
  against the platform JWKS. Shared deterministic sim → prediction + reconciliation
  + interpolation. Use it when you want maximum wire efficiency + your own
  transport. Live: https://tank-production-5873.up.railway.app
- Full catalog of live apps with URLs: see
  [references/publishing.md](references/publishing.md).
