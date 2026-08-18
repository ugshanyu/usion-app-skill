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
| [references/game-engines.md](references/game-engines.md) | The app is a real 2D/3D game — the blessed platform-hosted engine runtimes (Phaser 4; Babylon.js + Havok with its ready-made `PhysicsCharacterController`), the exact allowed `<script>` tags, and engine-specific multiplayer wiring |
| [references/publishing.md](references/publishing.md) | You're deploying/registering the app — hosting paths, service registry, and links to live deployed exemplar apps |
| [references/agent-api.md](references/agent-api.md) | You're an AI agent registering/managing services via the REST API with a creator API key — auth, `POST /services`, capturing the one-time signing secret, rotating it |

## Step 1 — Decide the delivery path

There are two ways an app reaches users. Pick one first; it changes everything
about structure and deploy.

**Path A — Static bundle (AI-Creator style).** One self-contained `index.html`
(CSS + JS inlined, no build step, no external CDNs — the ONLY exception is the
platform-hosted engine runtimes under `https://usions.com/vendor/`, see
[references/game-engines.md](references/game-engines.md); other external
scripts are stripped at deploy). Hosted on S3 by the
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
  never invent custom payment flows. ⚠️ A charge is an ESCROW HOLD: your server
  MUST settle the returned `receiptToken` (`POST /wallet/receipt/settle`) or the
  platform auto-refunds the user after 72h and you earn nothing. Instant goods
  (hints, unlocks) settle immediately; failed work refunds. See "Settling is
  MANDATORY" in the SDK reference.
- Do NOT build room codes, invite/share UIs, matchmaking UIs, or wager
  pickers — the platform owns those (rooms, matchmaking, `game_invite` chat
  flow). Your game receives `config.roomId` and `config.playerIds` already set.
  An in-game **waiting hall / ready screen IS required** for multiplayer (see
  the game checklist below and the multiplayer reference) — it's the room the
  chat invite leads to, duels included.

Design: mobile-first, small embedded frame, Vercel-inspired minimalism
(black/white, flat, generous whitespace). Respect `Usion.getTheme()` and
`Usion.getLanguage()` — don't hardcode user-facing strings to one locale.

## Step 3 — Pick your capabilities

Quick map of what the platform offers (full signatures in the SDK reference):

- **Identity**: `Usion.user.getId/getName/getAvatar/getProfile`
- **Money**: `Usion.wallet.getBalance/hasCredits/requestPayment/onBalanceChange` — every `requestPayment` receipt must be settled server-side or it auto-refunds in 72h (SDK reference → "Settling is MANDATORY")
- **Durable storage** (per user, per app): `Usion.storage.get/set/remove/clear/keys` is database-backed, survives logout/reinstall/device changes, and keeps a device-local offline cache (512 KB/value); `Usion.fileStorage` remains device-local for base64 blobs
- **Cloud KV** (server-persisted, cross-device): `Usion.cloud.get/set/remove/keys` + shared per-app bucket `Usion.cloud.shared.*` with atomic `shared.incr` — 64 KB/value, 200 keys & 1 MB/bucket, 60 ops/min
- **Multiplayer**: `Usion.game.connect/join/action/realtime` + `on*` handlers; netcode helpers (interpolation, prediction, delta snapshots, lockstep, WebRTC mesh, WebTransport, `Usion.netcode.createInterestGrid` AOI spatial hash). World rooms (SDK ≥ 2.23): tag `world` + `Usion.game.joinWorld()` for drop-in/drop-out rooms with backfill — up to 200 players direct/hosted, 32 on the platform relay; hosted mode (`realtime.connection_mode: "hosted"` + a one-file server bundle the platform runs) — see the multiplayer reference
- **Launch mode**: `Usion.getLaunchParams().mode` is `'single'` (opened from Explore / the Game hub, solo) or `'multiplayer'` (opened from a chat game invite); `Usion.game.isMultiplayer()` is the boolean. Branch your setup on it — don't infer mode from `roomId`, the host declares it. (SDK ≥ 2.18)
- **Social**: `Usion.lobby.*` (parties + codes), `Usion.matchmaking.find/cancel/onMatch`, `Usion.leaderboard.submit/top/friends/me`
- **Records & leaderboards** — **every game enables this** (see the game checklist in Step 3.5). Set `leaderboard: {enabled: true, order: "desc"|"asc", max_score?}` on the service and call `Usion.leaderboard.submit(score)` on game over. You get the platform's records loop for free: your game appears in **Game Center** (players see their best + friends' records), and beating a friend's best auto-sends them a "«Name» beat your record" notification that reopens your game. Show `Usion.leaderboard.friends()` on your game-over screen. Reference app: **Flappy** (see references/publishing.md). Details in the SDK reference "Leaderboard + records" section.
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

## Step 3.5 — If you are building a GAME, this checklist is non-negotiable

Every one of these is how the platform's own games behave («13», Table Soccer,
Mini Golf, Sequence, Ludo). Full detail in
[references/multiplayer.md](references/multiplayer.md).

0. **If the game could be played with other people, build it multiplayer** —
   even when the request never says "multiplayer". Races, duels, quizzes,
   board and turn-based games, anything where a second player makes it better:
   ship the waiting hall + `Usion.game.invite()`. Only genuinely solo concepts
   (endless runner, personal puzzle, drawing toy) stay single-player, and they
   still submit scores so friends compete through the leaderboard. If the user
   explicitly asked for multiplayer, it is required — never ship a solo
   stand-in instead.
1. **Two entry points, two behaviours.** Branch on
   `Usion.getLaunchParams().mode`, never on `roomId`:
   - `'single'` (GameTok / Explore) → **start playing instantly** vs bots or
     solo. Zero taps: no menu, no difficulty picker, no waiting screen.
   - `'multiplayer'` (a friend's chat invite) → open the **waiting hall**.
   - A solo round can be promoted mid-session (host's Share button): register
     `Usion.game.onRoomAssigned` up front, tear down the bot round, show the
     waiting hall.
2. **Multiplayer games have a waiting hall.** Present players with avatars, a
   READY toggle each, host-only Start enabled once everyone present is ready
   (min 2), seat order locked into the match's first stored `action`, plus a
   "play with bots" escape hatch and `Usion.game.invite()` for more players.
   Required for 2-player duels too.
3. **Multiplayer games have in-game chat: quick phrases + free text.** A
   tap-to-send list of ~6–10 localized canned phrases plus a "type your own"
   input, sent with `Usion.game.realtime('quick_chat', {phrase})` (never
   `Usion.chat.sendMessage`), rendered as short-lived bubbles on the sender's
   seat. Rate-limit, cap the length, render with `textContent`, and hide the
   affordance in solo/bot rounds.
4. **Every game has a leaderboard, and it feeds Game Center.** Set
   `leaderboard: {enabled: true, order}` on the service and `submit()` on game
   over; show `Usion.leaderboard.friends()` + `top({limit:10})` on the
   game-over screen. No number? Submit wins, best time, or level reached.
   Report match outcomes with `Usion.game.reportResult({winnerId, ...})` so the
   result card lands back in the chat the game was started from.
5. **2+ players must not lag or glitch.** Host broadcasts at 15–20 Hz on a
   timer (never per rendered frame), guests interpolate instead of snapping,
   `realtime()` for per-frame state and `action()` for turns, apply exactly
   once in the handler (never optimistically *and* on echo), small quantized
   payloads. Verify with `Usion.game.simulateNetwork(...)`.
6. **Survive every disconnect.** Pause on `onDisconnect` / `onConnectionState`,
   resync from your own last sequence on return, a wall-clock heartbeat to
   detect mobile WebView freezes (no `visibilitychange` on React Native),
   checkpoint from whoever just acted, and a forfeit grace window (~20 s)
   before anyone is folded.
7. **Turn-based: the first move is random, and there's a grace clock.** Derive
   the starting seat from the seed in the match's first stored action — never
   `playerIds[0]`, or the person who sent the invite opens every single game —
   and re-roll it on a rematch. Then: wall-clock deadline per turn (not a tick
   counter), frozen while your own link is down and credited back on reconnect,
   auto-move on timeout, and a single elected client that plays for a stalled
   seat after a further grace window — a locked phone must never freeze the
   table.

8. **Be GameTok-ready.** Published games land in GameTok, a full-screen swipe
   feed, and in GameTok Party where a host swipes and everyone is dropped into
   the same game together. That means: instant play on `mode: 'single'` (a
   game that opens on a lobby is dead content in the feed); `onRoomAssigned`
   handled so a solo session can be pulled into a shared room at any moment;
   the whole viewport filled in portrait with one-thumb controls; as many
   players as the rules allow (parties run to 16, extras are benched until the
   next game); and a score submitted on every game over.

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

- ⭐ **«13» (Mongol Poker)** — https://github.com/nelsuh/13 (MIT, live at
  https://13-phi-ten.vercel.app). **The reference game: read it first.** Three
  files, no build step, and it implements every rule in the Step 3.5 checklist —
  launch-mode split (GameTok → instant bots round, invite → waiting hall),
  READY-gated waiting hall with host start, `onRoomAssigned` promotion, turn
  grace clock with an elected proxy move for a sleeping phone, forfeit grace,
  checkpoint+replay reconnect recovery, leaderboard/Game Center, `reportResult`,
  mn/en i18n. Copy its structure instead of inventing one.
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
- `microservices/orbs-hosted` + `microservices/orbs-direct` — the **massive
  multiplayer twins** (SDK ≥ 2.23): the same agar.io-lite world game (200
  players, drop-in/drop-out, AOI) implemented BOTH ways. `orbs-hosted` is the
  hosted-mode reference (server.bundle.js on the platform rooms runtime —
  you write rules, the platform runs tick/AOI/auth); `orbs-direct` is the
  developer-hosted reference (own Node server: JWKS auth, 30 Hz sim / 15 Hz
  AOI snapshots, seq discipline, keepalives). Diff the two to see exactly
  what hosted mode does for you. Not yet deployed — in-repo reference.
- Full catalog of live apps with URLs: see
  [references/publishing.md](references/publishing.md).
