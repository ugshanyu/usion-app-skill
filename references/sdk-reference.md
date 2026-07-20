# Usion SDK — full API reference

Source of truth: `packages/sdk/src/modules/*.js` and `packages/sdk/types/index.d.ts`
(npm `@usions/sdk`, version in `packages/sdk/package.json` — 2.24.0 at time of
writing). The browser bundle is served at `https://usions.com/usion-sdk.js`.
If anything here disagrees with the source, the source wins.

> **Chat-list surfacing is automatic (SDK ≥ 2.15).** Your app appears in the
> user's chat list only after they *actually interact* with it — the first real
> tap/click/key/touch — not when it merely opens. The SDK detects this for you
> (an internal one-time `USER_INTERACTION` beacon); you don't need to call
> anything, and automatic load-time SDK calls never count as engagement.

## Contents

1. [Lifecycle & config](#lifecycle--config)
2. [User](#user) · [Wallet](#wallet) · [Session](#session)
3. [Storage (device-local)](#storage-device-local) · [File storage](#file-storage) · [Cloud KV](#cloud-kv-server-persisted)
4. [Game (multiplayer)](#game-multiplayer)
5. [Lobby](#lobby) · [Matchmaking](#matchmaking) · [Leaderboard](#leaderboard)
6. [Chat](#chat) · [Bot](#bot)
7. [Results, sharing, misc root methods](#results-sharing-misc)
8. [Hybrid tabbed services](#hybrid-tabbed-services-sdk--225)
9. [UI utilities](#ui-utilities)
10. [Backend channel & allowlist](#backend-channel)
11. [Error model](#error-model-sdk--222)
12. [APIs that DO NOT exist](#apis-that-do-not-exist)

## Lifecycle & config

```javascript
Usion.init(callback)   // callback(config) — fires once config arrives from host
Usion.init()           // ALSO returns Promise<config> (SDK ≥ 2.22): await Usion.init()
Usion.init({timeout: 8000})  // rejects UsionError(INIT_TIMEOUT) if the host never
                             // sends INIT (embedded but host silent) — no more
                             // hanging forever; a late INIT still fires the callback
Usion.version          // SDK version string
Usion.config           // read-only current config
Usion.getLaunchParams() // {path, ref, roomId, mode} — how the host opened this app
```

`config` fields: `userId, userName, userAvatar, authToken, sessionId,
sessionData, balance, results, theme ('light'|'dark'), language, socketUrl,
webTransportUrl, roomId, playerIds, serviceId, serviceName, apiUrl,
connectionMode ('platform'|'direct'), launchPath, ref, mode`.

### The auth token: scoped, late, and refreshed (read it LIVE)

`config.authToken` is a **scoped iframe token** (JWT with `purpose: "iframe"`,
bound to YOUR service id, ~60-min TTL) — never the user's full JWT. Three
contracts every app with its own backend must follow:

- **It can be absent at first INIT.** The host sends INIT immediately and mints
  the token in parallel, so the first seconds of a session are legitimately
  tokenless; the token arrives via a follow-up INIT (the SDK ≥ 2.24.1 merges it
  into `Usion.config.authToken` / `Usion.user.getToken()` without re-firing your
  init callback). Don't fire authenticated requests the instant init fires —
  wait/spinner until the token exists, and on a 401 wait briefly for a fresh
  token and retry once before showing an error.
- **Read it per request, never cache the boot value.** The host re-mints and
  re-INITs before the 60-min expiry; `Usion.config.authToken` and
  `Usion.user.getToken()` always hold the current token. A copy taken at init
  goes stale and turns into 401s an hour in.
- **Your server verifies it with `POST {apiUrl}/iframe/verify-token`**, body
  `{"token": "...", "expected_service_id": "<your service id>"}` →
  `{user_id, name, avatar}`. Do NOT send it to `/auth/me` — user-facing
  endpoints reject iframe-scoped tokens by design. Never trust a client-claimed
  user id; verify server-side and cache briefly. Game-room REST endpoints
  (`POST /games/rooms`, `/games/rooms/{id}/join`, `GET /games/rooms/{id}`,
  matchmake) DO accept the scoped token — but only for rooms of your own
  service.

**Single vs multiplayer (SDK ≥ 2.18):** `Usion.getLaunchParams().mode` is
`'single'` (opened from Explore / the Game hub, played solo) or `'multiplayer'`
(opened from a game invite in a chat). The host declares it authoritatively —
branch on it to skip lobby/matchmaking UI in single-player or wire up netcode in
multiplayer. `Usion.game.isMultiplayer()` is the boolean shortcut. Don't infer
mode from `roomId` yourself: a single-player game may still get an auto-created
room, so trust `mode`. A `'single'` launch can be PROMOTED into a multiplayer
room after launch when the user taps the host's Share button — see
`Usion.game.onRoomAssigned` (SDK ≥ 2.20): `roomId`/`mode` update and the SDK
auto-joins. So register multiplayer handlers up front even in `'single'`.

**Deep-linking:** when the user taps a notification carrying a `path`, the app
reopens and `Usion.getLaunchParams().path` returns that path. Read it in your
`init` callback and route to the right screen (the host never drives your
internal router — it just hands you the path). Example:

```javascript
Usion.init(() => {
  const { path } = Usion.getLaunchParams();
  if (path) router.go(path);   // your app's own routing
});
```

Contexts: **embedded** (iframe/WebView — everything relayed via postMessage to
the host's authenticated socket), **standalone** (own Socket.IO socket; needs
`socketUrl` + token), **direct** (game-server WebSocket). The SDK auto-detects;
you normally just call `Usion.game.connect()`.

## User

```javascript
Usion.user.getId()      // string|null  (sync)
Usion.user.getName()    // string|null
Usion.user.getAvatar()  // string|null
Usion.user.getToken()   // JWT for socket connections (used internally)
Usion.user.getProfile() // Promise<{id, name, avatar}>
```

## Wallet

Credits only — never move money any other way.

```javascript
Usion.wallet.getBalance()                       // Promise<number> (cached, refreshed on BALANCE_UPDATE)
Usion.wallet.getBalance({fresh: true})          // bypass the cache — after server-side settles/refunds
Usion.wallet.hasCredits(amount)                 // Promise<boolean>
Usion.wallet.requestPayment(amount, reason, opts?)
// → Promise<{success, newBalance?, receiptToken?, transactionId?}>
// Host shows a confirmation dialog; resolves with a receiptToken your SERVER
// later settles/refunds. Rejects on decline, or only after confirming no charge
// happened.
Usion.wallet.onBalanceChange(cb)                // cb(balance)
```

### Charging safely (idempotency + recovery)

The charge is debited the moment the user confirms; you get a `receiptToken`
your server settles (work succeeded) or refunds (work failed).

- **Reliability is built in.** If the confirmation message is lost (flaky
  network, backgrounded tab), the SDK re-queries the host and recovers the
  `receiptToken` instead of failing — so a paid charge is never stranded. You
  don't have to do anything for this.
- **Make retries safe with an idempotency key.** If your app might call
  `requestPayment` twice for the same thing (a retry button, an auto-retry on
  error), pass a stable `idempotencyKey`. The platform dedupes on it: the user
  is charged **at most once** and both calls return the **same** `receiptToken` —
  no second dialog.

```javascript
// One purchase "intent" → one stable key (reuse it across retries).
const key = `buy-pack-${userId}-${packId}`;
const { receiptToken } = await Usion.wallet.requestPayment(100, 'Pack of 100', { idempotencyKey: key });
// Hand receiptToken to YOUR server; settle/refund it after the work runs.
```

Omit `opts` (or `idempotencyKey`) for the simple one-shot behavior.

## Session

Ephemeral per-open state, synced to the host.

```javascript
Usion.session.getId()
Usion.session.getData(key?)              // all data or one key
Usion.session.setData(key, value)        // or setData({k1: v1, k2: v2})
Usion.session.clear()
```

## Storage (device-local)

Per-user, per-service KV on the device (localStorage/AsyncStorage). 512 KB per
value. Survives restarts, NOT reinstall or device change — cache-grade state.

```javascript
Usion.storage.get(key)     // Promise<any|null>
Usion.storage.set(key, value)
Usion.storage.remove(key)
Usion.storage.clear()
Usion.storage.keys()       // Promise<string[]>
```

## File storage

Binary blobs (IndexedDB / filesystem), per-user per-service.

```javascript
Usion.fileStorage.set(key, base64Data, mimeType)  // base64 WITHOUT data: prefix
Usion.fileStorage.get(key)    // Promise<{base64Data, mimeType}|null>
Usion.fileStorage.remove(key)
```

## Cloud KV (server-persisted)

SDK ≥ 2.11, enabled for every service. Cross-device. Backend:
`backend/realtime/kv_handlers.py`, Mongo collection `service_kv`.

**Quotas:** 64 KB/value · 200 keys/bucket · 1 MB total/bucket · 60 ops/min per
user per service. Keys 1–128 chars, charset `A-Za-z0-9_.-:/`.

```javascript
// Per-user bucket (cross-device saves)
Usion.cloud.get(key)            // Promise<any|null>
Usion.cloud.set(key, value)     // Promise<{success, size}>
Usion.cloud.remove(key)         // Promise<{success, removed}>
Usion.cloud.keys()              // Promise<string[]>

// Shared per-app bucket (all users)
Usion.cloud.shared.get/set/remove/keys(...)
Usion.cloud.shared.incr(key, delta?)   // Promise<number> — atomic counter
```

## Game (multiplayer)

### Connection & rooms

```javascript
await Usion.game.connect()            // REQUIRED before join; auto-picks transport
await Usion.game.join(config.roomId)  // → {room_id, player_id, sequence?}
Usion.game.leave()
Usion.game.disconnect()
Usion.game.isConnected()              // boolean
Usion.game.isMultiplayer()            // boolean — launched from a chat invite vs solo from Explore (SDK ≥ 2.18)
Usion.game.connectDirect({roomId?, serviceId?, apiUrl?, token?, liveness?, backpressureBytes?})  // force direct-mode WS
//   Direct sockets self-heal (SDK ≥ 2.24): a liveness watchdog probes after 4 s of inbound
//   silence and declares the connection dead at 12 s (reason 'liveness_timeout') so
//   auto-reconnect starts in seconds, not at TCP timeout; reconnects reuse the cached access
//   token while it has >30 s validity (single WS dial); realtime input frames are held
//   latest-only when the send buffer backs up past 8 KB (control frames always send).
//   Tune via liveness: {probeAfterMs?, deadAfterMs?} | false and backpressureBytes (0 = off).
Usion.game.getNetworkStats()          // {transport, connectionState, quality, rtt, jitter, lastInboundAgeMs, bufferedAmount} (SDK ≥ 2.24)
Usion.game.onNetworkQuality(cb)       // fires on quality TRANSITIONS: {quality: 'good'|'fair'|'poor'|'dead', prev, stats} — returns unsubscribe (SDK ≥ 2.24)
await Usion.game.joinWorld({serviceId?})  // → {roomId, playerIds} — drop-in/drop-out WORLD placement (SDK ≥ 2.23)
//   Services tagged `world`. Rides the mm channel (embedded AND standalone): returns the world
//   you're already in, else backfills a world with space, else creates a fresh one. Sets
//   game.roomId, so the usual connect()+join() (relay) or connectDirect() (direct/hosted) flow
//   is unchanged afterwards. Rejects MATCH_TIMEOUT after 15 s; join() on a full world rejects
//   WORLD_FULL (seats free on leave/prune — see references/multiplayer.md "World rooms").
```

### Sending

```javascript
Usion.game.action(type, data?, opts?)  // Promise<{success, sequence?}> — sequenced + stored; turn-based moves
//   opts.nextTurn:     player ID whose turn is next — server remembers it and hands it to
//                      (re)joining clients as current_turn, so turn state survives reconnects
//   opts.queueOffline: hold the move while disconnected and send it (in order) on reconnect
//                      (turn-based only — never for realtime, which would replay stale inputs)
Usion.game.realtime(type, data?)  // fire-and-forget — per-frame state, positions, effects
Usion.game.requestSync(lastSeq?)  // ask server for full state → onSync (auto-called on reconnect)
Usion.game.requestRematch()
Usion.game.forfeit()              // Promise<{success}>
Usion.game.invite(opts?)          // open host friend/group picker → fill your room (SDK ≥ 2.19)
//   Promise<{success, roomId, invited[]}>. Recent chats + username search + your groups,
//   multi-select; each pick gets a game-invite card; tappers join THIS room → onPlayerJoined.
//   Works even if launched solo: the host makes a room with you as host and joins you to it.
//   opts.maxPlayers caps the room; selection is capped at remaining seats. Embedded-only.
Usion.game.getLastSequence()        // highest action sequence seen (SDK ≥ 2.21)
Usion.game.getLastAppliedSequence() // highest applied locally; trails while catching up (≥ 2.21)
Usion.game.setState(state)          // checkpoint authoritative state server-side (≤ 64 KB)
//   Sequence-versioned (SDK ≥ 2.22): the SDK sends the action sequence the state
//   reflects; the server REJECTS older checkpoints → resolves
//   {success:false, code:'STALE_STATE'}. Recover by resyncing, don't retry blindly.
```

**Self-healing sends (SDK ≥ 2.22):** if the server reports the socket isn't in
the room (`NOT_IN_ROOM` — a reconnected-but-detached socket), the SDK
auto-rejoins + resyncs and retries the action once. `realtime()` failures are
no longer silent either — they ack a coded error surfaced via `onError`
(`{code, message, source: 'realtime'}`).

### Reconnect-safe shared state (SDK ≥ 2.21)

```javascript
// Authoritative state that SURVIVES a disconnect — built on action()+setState().
// Host (player_ids[0]) auto-checkpoints; (re)joining clients recover automatically.
const s = Usion.game.syncedState(initial, {
  reduce: (state, a) => nextState,  // a = {playerId, type, data, sequence}; default shallow-merges data
  checkpointEvery: 1,               // host setState() cadence (1 = exact recovery); 'authority': 'host'|'all'
});
s.get();                  // current state      s.onChange(cb)        s.isAuthority()
s.commit(data) / s.commit(type, data, opts);    // sequenced + applied once; recovers on rejoin
s.checkpoint();           // force a server checkpoint (authority only; no-op in direct mode)
s.getSequence();          // sequence of the last action applied      s.destroy() // detach
```

### Handlers

```javascript
Usion.game.onJoined(d)         // local join confirmed
Usion.game.onPlayerJoined(d)   // d.player_id, d.player_ids (full updated roster)
Usion.game.onPlayerLeft(d)     // d.player_id
Usion.game.onRoomAssigned(d)   // d.roomId — host promoted a SOLO launch into a room (SDK ≥ 2.20)
Usion.game.onStateUpdate(d)    // d.game_state, d.current_turn, d.sequence
Usion.game.onSync(d)           // d.actions[], d.game_state, d.sequence
Usion.game.onAction(m)         // m.player_id, m.action_type, m.action_data, m.sequence
Usion.game.onRealtime(m)       // m.player_id, m.action_type, m.action_data
Usion.game.onGameFinished(d)   // d.winner_ids[], d.reason?, d.forfeiter?
Usion.game.onGameRestarted(d)  // rematch; sequence resets to 0
Usion.game.onRematchRequest(d)
Usion.game.onError(d)          // d.message, d.code (stable ERROR_CODES value), d.source?
Usion.game.onDisconnect(reason) / onReconnect(attempt) / onConnectionError(err)
Usion.game.onPlayerConnection(d)  // a peer's connection state changed (transient drop/recover)
// SDK ≥ 2.21 — unified reconnection lifecycle (use these for the "Reconnecting…" UX):
Usion.game.onConnectionState(s)   // 'connected'|'disconnected'|'rejoining'|'reconnected'; same on all transports
Usion.game.getConnectionState()   // current state, synchronously
Usion.game.onReconnected(info)    // once after a reconnect's re-sync: info.{state, lastSequence, viaSync}
```

Each `onX(cb)` keeps a SINGLE handler (last registration wins) but returns an
unsubscribe function. For multiple listeners on the same event use
`Usion.game.on(event, cb)` — it supports any number of listeners, can be called
BEFORE `connect()`, works in every transport, and returns an unsubscribe
function. It accepts the internal name (`'action'`), the wire name
(`'game:action'`), or snake_case (`'player_joined'`).

### Solo → host promotion (SDK ≥ 2.20)

A game opened SOLO (launch `mode: 'single'`, from Explore / the Game hub) can be
promoted into a live multiplayer room AFTER launch — when the user taps the
host's top-bar **Share** button and sends an invite. The host posts the new room
into the iframe and the SDK handles the rest:

```javascript
Usion.game.onRoomAssigned((d) => {
  // d.roomId — the SDK has ALREADY set getLaunchParams().roomId + .mode = 'multiplayer'
  // and is connect()+join()ing this room for you. onJoined fires right after.
  flipToMultiplayerView();   // swap the solo view for the hosting/multiplayer view
});
```

When this fires, the caller becomes the host (`playerIds[0]`) and invitees join
the SAME room. Because any multiplayer-capable game can be promoted mid-session,
register your multiplayer handlers (`onPlayerJoined`, `onAction`/`onRealtime`,
`onJoined`) UP FRONT — don't gate them behind `isMultiplayer()`/`mode` at launch.
`getLaunchParams().mode` stays `'single'` as the LAUNCH value, but `roomId`
becomes set once promoted. Don't build your own Share/invite UI — the host owns
it (see `Usion.game.invite()` and the multiplayer reference).

### State persistence (iframe remount recovery)

```javascript
Usion.game.saveState(state)  // localStorage keyed by player+room → boolean (device-local)
Usion.game.loadState()       // T|null
Usion.game.clearState()
Usion.game.debug(payload)    // host overlay when page has ?debug=1

// Server-side authoritative checkpoint (any participant may call, not host-only, ≤64 KB).
// Distinct from saveState (which is device-local localStorage): the checkpoint
// is sent to every client that joins/rejoins as `game_state` in the join ack
// and in game:sync, so reconnect recovery becomes "load checkpoint + replay the
// tail" instead of replaying every action from zero.
Usion.game.setState(state)   // Promise<{success, error?, code?}>; no-op in direct mode
```

### Netcode helpers (also under `Usion.netcode.*`)

Transport-agnostic, zero-dependency. See `references/multiplayer.md` for usage.

```javascript
Usion.game.diff(prev, next) / patch(base, delta) / quantize(value, precision)
Usion.game.encode(value) / decode(buf)                  // compact binary
Usion.game.createInterpolation({serverFps?, bufferMs?, adaptive?, ...})
Usion.game.createPredictor({apply, initialState?, smooth?})
Usion.game.createSnapshotSender({hz?, channel?, delta?, keyframeEvery?, precision?, encode?, source?})
Usion.game.createSnapshotReceiver({decode?})
Usion.game.createSender({hz?})            // coalescer: queue()/append()/flush()
Usion.game.createLockstep({playerId, players, step, inputDelay?})
Usion.game.createLagCompensator({historyMs?})   // server-side rewind
Usion.game.createMesh({role: 'host'|'guest', iceServers?})        // 2-peer WebRTC
Usion.game.createMeshNetwork({...})       // N-player full mesh
Usion.game.createWebTransport({url?})     // HTTP/3 datagrams
Usion.game.replicate(obj, {hz?, channel?, precision?})  // host: mutate, auto-sync
Usion.game.replica({channel?, interpolate?})            // client: receive + view()
Usion.game.simulateNetwork({latencyMs?, jitterMs?, lossPct?, dupPct?} | null)
Usion.game.ping()    // Promise<number|null> RTT ms
Usion.game.getRtt()  // smoothed RTT
Usion.game.createInterestGrid({cellSize?})  // spatial-hash AOI for world rooms (SDK ≥ 2.23) — below
```

**Interest grid (SDK ≥ 2.23)** — the area-of-interest building block for world
rooms: buckets entities into fixed-size cells so "who is near (x, y)?" costs a
few cell lookups instead of an O(N) scan. Pure JS with no DOM/window
references — the same helper runs in the browser and in a Node game server
producing per-player snapshots.

```javascript
const grid = Usion.netcode.createInterestGrid({ cellSize: 256 });
//   cellSize (world units) defaults to 256 — pick roughly the typical query
//   radius so lookups touch ~4–9 cells. Ids: non-empty string | finite number.
grid.upsert(id, x, y)     // insert or move an entity
grid.remove(id)           // unknown ids are a no-op
grid.query(x, y, radius)  // → ids within radius (true circle test, not just cell membership)
grid.observe(observerId, x, y, radius)  // → {entered, left, visible} — like query(), but
//   diffed against this observer's previous observe(): drive spawn/despawn from
//   entered/left and per-tick snapshots from visible
grid.dropObserver(observerId)  // free the observer's tracking state (call when a player leaves)
grid.size()               // number of entities in the grid
```

Allocation notes: `observe()` swaps two persistent per-observer sets instead of
reallocating (it runs per tick per observer); a query scans only the cells the
circle's bounding box overlaps, then applies a per-entity circle test.

## Lobby

Parties with invite codes. Rides the backend channel (`lobby:*`).

```javascript
Usion.lobby.state            // {code, host, status, members: [{id, name?, ready}]}
Usion.lobby.create({maxPlayers?, public?})  // Promise<{code}> — you become host
Usion.lobby.join(code)       // Promise<{code}>
Usion.lobby.leave()
Usion.lobby.setReady(ready?) // default true
Usion.lobby.allReady()       // boolean (sync)
Usion.lobby.isHost()         // boolean
Usion.lobby.start(roomId)    // host only
Usion.lobby.queue(serviceId, {conversationId?})  // create/find a room via REST
Usion.lobby.onUpdate(cb) / onStarted(cb)  // cb({room_id, by, player_ids?})
```

## Matchmaking

Queue with strangers (`mm:*`).

```javascript
Usion.matchmaking.find(serviceId?, {size?, timeout?})  // Promise<{roomId, players[]}> — size default 2
//   timeout (ms, SDK ≥ 2.22): bound the wait — on expiry the SDK leaves the
//   queue and rejects UsionError(MATCH_TIMEOUT). Without it, find() stays
//   pending until matched or cancel()led. A newer find() rejects the previous
//   one with SUPERSEDED; cancel() rejects with CANCELLED.
Usion.matchmaking.cancel()
Usion.matchmaking.onMatch(cb)
```

## Leaderboard + records

**If your game has a score, a high score, or a time — enable this.** It is the
platform's built-in retention loop, and it's almost free: opt in on the service
config and call `submit()` on game over. The platform does the rest.

Service config (set at registration / publish):

```json
"leaderboard": { "enabled": true, "order": "desc", "max_score": 100000 }
// order: "desc" = higher is better (default) · "asc" = lower is better (time trials, golf)
// max_score (optional): scores beyond this still record but never fire record
//   notifications — a plausibility guard against forged scores.
```

```javascript
Usion.leaderboard.submit(score, metadata?)  // Promise<{success, score, best, rank, updated}>
Usion.leaderboard.top({limit?})             // Promise<entries[]> — global, default 20
Usion.leaderboard.friends({limit?})         // your accepted friends + you (powers Game Center)
Usion.leaderboard.me()                      // Promise<{score, rank, total}>
// entry: {user_id, name?, avatar?, score, rank, is_me, metadata?}
```

**What you get for free once `leaderboard.enabled` + you `submit()`** — no extra
code:

- **Game Center**: your game shows up in the platform's records hub — every
  player sees their best, their rank among friends, and their friends' records
  for your game, with a tap-to-play button.
- **"Friend beat your record" notifications**: when a player's new best
  overtakes a friend's best, that friend automatically gets a
  "«Name» beat your record on «YourGame»" message + push that opens your game.
  This is the platform's virality loop — you write zero code for it; it's a
  direct consequence of calling `submit()`.

**Recommended pattern for a score-based game** (this is what the Flappy
reference app does — see publishing.md):

```javascript
// on game over
const r = await Usion.leaderboard.submit(score);   // best kept automatically
showBest(r.best);
const friends = await Usion.leaderboard.friends();  // render the friends board
renderRecords(friends);  // {name, avatar, score, rank, is_me} — highlight is_me
```

Submit only real, earned scores (the server keeps the best per player, so
submitting every run is fine). `friends()`/`top()` are safe to call anytime
after `Usion.init`.

## Chat

Host shows confirmation dialogs — apps can't message silently.

```javascript
Usion.chat.sendMessage(recipientId, message)   // Promise<{success, reason?}>
Usion.chat.createPersonalChat(peerUserId)      // Promise<{chatId, peerName?, ...}>
```

## Bot

For inline bot iframes (widgets in chat bubbles).

```javascript
Usion.bot.callAction(action, data?)  // → iframe_action webhook, Promise<any>
Usion.bot.sendMessage(text)          // simulate user message
Usion.bot.updateContext(ctx)
Usion.bot.close(result?)
Usion.bot.onMessage(cb)              // cb({id, content, components?, sender_id})
```

### Push notifications

When a service/bot message reaches a user who is **offline**, the user now gets a
push notification showing the **service/bot name** + the **message preview** (text,
or `📷 Photo` / `🎵 Voice message` / `📍 Location` / `🎮 <game>` for media/components).
Tapping it opens the chat. No setup needed — it fires automatically on send.
Personal 1-on-1 messages stay end-to-end encrypted, so their pushes show the sender
name but a generic body ("Sent you a message"), never decrypted content.

## Permissions

Ask the user before using a capability — the same way you ask for money. The host
shows a modal; the user **allows or cancels**. The user can later change any grant
in the Usion app's settings for your app. SDK ≥ 2.17. First permission:
`notifications`. Backend: per-user-per-service grants in `service_permissions`.

```javascript
Usion.permissions.request(['notifications'], { reason? })  // Promise<{granted, permissions}>
Usion.permissions.query(['notifications'])                 // Promise<{notifications:boolean}>  (no prompt)
Usion.permissions.has('notifications')                     // Promise<boolean>
```

- **Ask before you act.** Capabilities are enforced by the platform, not by your
  return value — e.g. `notify.send` is dropped (`delivered:'blocked'`) until the
  user grants `notifications`. Pattern: `request` first, then use the capability.
- **`granted`** is true only if EVERY requested permission ended granted;
  **`permissions`** is the per-key result map.
- **You can't grant yourself.** The trusted host writes the grant, never the
  iframe — `request` just shows the modal.
- **Embedded feature.** Standalone (outside the Usion app) there's no modal;
  `request`/`query` resolve "not granted" and the user manages grants in-app.

## Notify

Let your app notify ITS OWN user — even when they aren't looking at it. Delivery
is context-aware: an in-app banner when the user is online elsewhere in Usion, an
OS push when they're offline or the app is backgrounded. Tapping reopens your app
(at `path`, if given). SDK ≥ 2.13. Backend: `backend/realtime/notify_handlers.py`.

```javascript
// REQUIRED once before sending — without a grant, send() returns delivered:'blocked'.
await Usion.permissions.request(['notifications']);
Usion.notify.send({ title, body, path? })  // Promise<{success, delivered}>
Usion.notify.setMuted(muted)               // user opt-out for this app
Usion.notify.isMuted()                     // Promise<boolean>
```

- **The notification title is ALWAYS your mini-app's name** — so the user can
  tell which app pinged them (every mini-app shares the Usion app identity).
  Your `title` becomes the message headline and `body` the detail; both render in
  the notification body (banner and OS push alike). Don't put your app name in
  `title` — put the actual message there.
- `path` deep-links into your app — a safe **relative** path (`/render/abc`);
  read it back on launch via `Usion.getLaunchParams().path`.
- **Scope:** you can only notify the **current** user — never fan out to others.
- **Limits:** ≤ 20 notifications/hour per user per service; `title` ≤ 80 chars,
  `body` ≤ 200, `path` ≤ 512. Muted services are silently dropped.
- **Server-triggered** (job finishes while the app is closed): your own backend
  calls the signed `POST /services/{id}/notify` — see `references/publishing.md`.

## Results, sharing, misc

```javascript
Usion.saveResult(data, {thumbnail_url?, title?, type?})  // server-persisted, Promise<SavedResult>
Usion.deleteResult(resultId)
Usion.getResults()                   // SavedResult[] from init config

Usion.share(contentType, data)       // 'audio'|'image'|'video'|'text'|'mixed'; native share sheet
Usion.shareToFeed(contentType, data) // Promise<{success, postId?, shareUrl?}>
Usion.download(url, filename?)       // save to device/gallery

Usion.submit(data)                   // finish with results; host closes the app
Usion.exit({backCount?})             // close the mini-app
Usion.error(message)
Usion.log(msg)
Usion.on(type, cb)                   // custom postMessage events from host (NOT socket events); returns unsubscribe fn
Usion.diagnostics()                  // {version, transport, connected, joined, roomId, playerId, lastSequence, ...}
                                     //   live SDK snapshot — also auto-attached to game.debug payloads
Usion.getTheme()                     // 'light'|'dark'
Usion.getLanguage()                  // e.g. 'en', 'mn'
Usion.claimBackButton(cb) / Usion.releaseBackButton()
```

### Back button: the claim is ONE-SHOT — re-claim per screen

`Usion.claimBackButton(cb)` routes the HOST header's back button to your app —
use it instead of drawing your own header. But the claim resets after a
single press (host and SDK both), so **claiming once at boot gives you exactly
one working back press**; after that the button silently closes your app. The
correct pattern: re-claim on **every screen change** while an in-app "back"
exists, and `releaseBackButton()` on your root screen so the host button
becomes a plain close there:

```javascript
function showScreen(render, onBack) {
  render();
  if (onBack) Usion.claimBackButton(function handle() {
    onBack();                       // navigates → next showScreen re-claims
    if (currentScreenHasBack()) Usion.claimBackButton(handle); // safety net
  });
  else Usion.releaseBackButton();   // root screen: host shows ✕ (close)
}
```

## Hybrid tabbed services (SDK ≥ 2.25)

A **bot** service that also registers `tabs` (see the publishing reference)
gets a hybrid host screen: the platform's **native bot chat** is one tab, and
your app's own pages are the other tabs — rendered in ONE persistent
iframe/WebView that stays mounted across tab switches. Chat traffic rides the
normal bot webhook + Bot API; these SDK methods are only the screen bridge:

```javascript
// Host → app: the user tapped one of your tabs (or a deep link targeted one).
Usion.onHostNavigate(({ path, tab }) => showSection(path)); // tab = key or null
Usion.offHostNavigate();

// App → chat: switch to the native chat tab with the composer PRE-FILLED.
// Never auto-sends — the user reviews the text and presses send.
Usion.openChat({ prefill: 'Remix this video with a sunset sky' });

// App → tab bar: keep the host's tab highlight in sync when the user
// navigates INSIDE your app (fire-and-forget; never echoed back to you).
Usion.reportPath('/results');
```

Rules:
- **Detect hosting via `Usion.config.hostTabs === true`** (set in the INIT
  config only when the hybrid screen hosts you). When true, hide your own
  in-app tab bar / chat UI — the host renders the tab bar and the chatbot
  lives in the native chat tab. When absent (legacy full-screen iframe opens,
  old app versions), keep your own chrome working.
- **Subscribe early.** Calling `onHostNavigate` signals the host that your app
  navigates in place. If you never subscribe, every tab switch **remounts**
  your app with the new path delivered as `Usion.getLaunchParams().path`
  (deterministic fallback — but a full reload, so subscribe if you're a SPA).
- `HOST_NAVIGATE` always updates `getLaunchParams().path`, subscriber or not —
  reading it stays truthful at any time.
- Tab `path`s are relative paths inside your app (`"/explore"`), declared at
  registration; the chat tab has no path. Notification deep links
  (`Usion.notify.send({ path })`) land on the matching tab.
- **Chat → tab buttons**: your bot may send a component button whose
  `action_id` is `"open_tab:<path>"` (e.g. `"open_tab:/results"`) — the hybrid
  screen intercepts it client-side and jumps to the matching tab. Buttons with
  any other `action_id` do NOT reach your webhook (interactions ride a legacy
  path) — use plain text replies for decisions.

## UI utilities

```javascript
Usion.setLoading(btnOrSelector, loading)   // usion-btn-loading class + disable
Usion.toggle(elOrSelector, show)
Usion.charCount(input, counter, max)
Usion.selectionGrid(containerSel, itemSel, onChange)  // → {getSelected(), clear()}
```

Design tokens: `https://usions.com/usion-design-system.css`.

## Backend channel

`Usion._backendEmit(event, data)` routes through the app's own socket
(standalone) or the host's authenticated socket (embedded). Standalone apps
don't need to call `Usion.game.connect()` first — the first cloud /
leaderboard / notify / lobby / matchmaking call connects automatically
(SDK ≥ 2.22). Embedded mode only
allows these prefixes: **`lobby:*`, `mm:*`, `lb:*`, `kv:*`, `notify:*`**. A new prefix
requires editing `BACKEND_EMIT_ALLOWED` in BOTH
`web/app/(main)/chat/iframe/[id]/game-handlers.ts` and
`mobile/features/iframe/message-handler.ts`, plus a backend
`register_*_handlers()` in `backend/realtime/` — and the mobile allowlist only
ships with the next EAS app release. Don't add prefixes casually.

## Error model (SDK ≥ 2.22)

Every SDK rejection is a **`UsionError`** with a stable machine-readable
`err.code` — branch on the code, NEVER on message text (messages may change
between releases; codes may not). The backend sends the code in every failure
ack; old backends fall back to message matching automatically.

```javascript
try {
  await Usion.cloud.set('save', bigBlob);
} catch (err) {
  if (err.code === 'VALUE_TOO_LARGE') { /* shrink the payload */ }
  if (err.code === 'RATE_LIMITED') { setTimeout(retry, err.retryAfter * 1000); }
}
```

Codes: `NOT_CONNECTED, NO_ROOM, ROOM_NOT_FOUND, NOT_PARTICIPANT, NOT_IN_ROOM,
WORLD_FULL, NOT_AUTHORITY, NOT_AUTHENTICATED, JOIN_TIMEOUT, CONNECT_TIMEOUT, INIT_TIMEOUT,
MATCH_TIMEOUT, STATE_TOO_LARGE, INVALID_STATE, STALE_STATE, INVALID_NEXT_TURN,
INVALID_INPUT, NOT_FOUND, QUOTA_EXCEEDED, VALUE_TOO_LARGE, LOBBY_FULL,
LOBBY_CLOSED, CONFLICT, RATE_LIMITED, REQUEST_TIMEOUT, QUEUE_FULL, CANCELLED,
SUPERSEDED, UNSUPPORTED, UNKNOWN`. `RATE_LIMITED` carries `err.retryAfter`
(seconds until the window resets). You rarely need to HANDLE `NOT_IN_ROOM` —
the SDK auto-rejoins and retries the action for you.

## APIs that DO NOT exist

Common hallucinations the platform's quality checker flags as
`fictional_sdk_call`:

- `Usion.ready` → use `Usion.init(cb)`
- `Usion.user.info` → use `Usion.user.getId()/getName()/getAvatar()`
- `Usion.game.emit` → use `Usion.game.action()` or `Usion.game.realtime()`
- `Usion.on(...)` for socket events in embedded mode → it only receives host
  postMessages; use `Usion.game.on*` handlers instead.
