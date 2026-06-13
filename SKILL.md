---
name: usion-app
description: >-
  How to build, test, and publish a mini-app or game for the Usion platform
  using the Usion SDK (@usions/sdk). Use this skill whenever the user wants to
  create, modify, or ship anything that runs inside Usion — a mini-app, a game
  (single-player or multiplayer), an iframe service, a chat widget, or a
  microservice — or asks what the Usion SDK can do (Usion.game, Usion.wallet,
  Usion.cloud, lobby, matchmaking, leaderboard, netcode). Also use it when
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

Beyond this skill, the repo ships reference-grade docs: `docs/sdk-guides/`
(six bilingual recipes — start here for a guided build), `docs/sdk-api/`
(generated TypeDoc), `docs/sdk-versioning-policy.md`, and the
`@usions/devkit` local dev harness (Step 5). Fastest start of all:
`npx @usions/devkit create <template>` then edit a working game.

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
  (or `onAction`) handlers.
- Money moves only through `Usion.wallet.requestPayment(amount, reason)` —
  never invent custom payment flows.
- Do NOT build lobbies, ready screens, room codes, invite UIs, or wager
  pickers — the platform owns those (rooms, matchmaking, `game_invite` chat
  flow). Your game receives `config.roomId` and `config.playerIds` already set.

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
- **Social**: `Usion.lobby.*` (parties + codes), `Usion.matchmaking.find/cancel/onMatch`, `Usion.leaderboard.submit/top/friends/me`
- **Chat integration**: `Usion.chat.sendMessage/createPersonalChat`, `Usion.bot.*` for inline bot widgets
- **Results & sharing**: `Usion.saveResult`, `Usion.share`, `Usion.shareToFeed`, `Usion.download`
- **Lifecycle/UI**: `Usion.exit()`, `Usion.claimBackButton(cb)`, `Usion.setLoading`, `Usion.toggle`, theme/language getters

Backend-channel modules (lobby `lobby:*`, matchmaking `mm:*`, leaderboard
`lb:*`, cloud `kv:*`) work both standalone and embedded automatically. Adding a
NEW event prefix requires allowlist changes in both hosts plus a backend
handler — see CLAUDE.md "Backend channel rule" before attempting.

## Step 4 — Multiplayer (if applicable)

Read [references/multiplayer.md](references/multiplayer.md). The core contract:

- The platform relays via Socket.IO; **`config.playerIds[0]` is the host** and
  the single source of truth (host-authoritative pattern).
- Host steps the simulation and broadcasts state with
  `Usion.game.realtime('state', {...})`; guests send inputs with
  `Usion.game.realtime('input', {...})`; host decides the winner and announces
  `realtime('gameover', { winner_id })`.
- `action()` is sequenced + stored (turn-based moves); `realtime()` is
  fire-and-forget (per-frame state). Never trust a peer's self-reported score
  for paid outcomes — compute on the host.
- Handle `onPlayerLeft` (forfeit/win), `onDisconnect`/`onReconnect`, and
  `onPlayerConnection` (peer `reconnecting`/`gone` during the grace window).
- **Reliability contract for turn-based games:** apply moves only on the
  `onAction` echo (the SDK dedups by sequence — never apply optimistically on
  send), pass `{ nextTurn }` and trust `current_turn`, and have the host
  checkpoint via `Usion.game.setState()`. This is what makes a game survive
  reconnects; the full recipe is `docs/sdk-guides/02-bulletproof-turn-based.md`.

## Step 5 — Test before calling it done

**The fastest path: `@usions/devkit`** — build and test a Usion game locally
with NO account, NO deployment, and NO second phone. The dev harness serves your
app in a fake host page that emulates the iframe protocol with the REAL relay
semantics (echo, sequences, sync):

```bash
npx @usions/devkit create turn-based-duel my-game  # or realtime-duel | solo-cloud
npx @usions/devkit dev ./my-game                   # serves on http://localhost:4747
# open http://localhost:4747/ and .../?player=2  → two tabs = two players, one room
npx @usions/devkit audit ./my-game                 # static pre-ship checks
```

The harness has latency/drop sliders and a **⚡ Blip connection** chaos toggle
that drops + auto-recovers the relay exactly like production — so you SEE your
reconnect UX (`onPlayerConnection: reconnecting → gone`) locally instead of
shipping and praying. The starter templates pass the chaos panel out of the box
and ARE the documentation most developers read — clone one before writing from
scratch. Not emulated: matchmaking/invites (the platform drops you into a room).

`usion audit` checks payload size (warn 2 MB / fail 5 MB), page basics
(viewport/lang/title), SDK usage, and — for multiplayer apps — the
reliability-contract handlers (`onAction`, `onSync`, `nextTurn`).

Other checks:
- Verify `Usion.init` fires (the SDK no-ops gracefully outside the host).
- Grep your own code for fictional SDK calls (`Usion.ready`, `Usion.game.emit`,
  `Usion.user.info`) — the platform's quality checker will flag them.
- Cloud KV end-to-end: `cd backend && python -m scripts.test_cloud_kv`.

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
- Full catalog of live apps with URLs: see
  [references/publishing.md](references/publishing.md).
