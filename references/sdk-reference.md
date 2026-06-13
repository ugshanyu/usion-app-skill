# Usion SDK — full API reference

Source of truth: `packages/sdk/src/modules/*.js` and `packages/sdk/types/index.d.ts`
(npm `@usions/sdk`, version in `packages/sdk/package.json` — 2.12.x at time of
writing). The browser bundle is served at `https://usions.com/usion-sdk.js`.
If anything here disagrees with the source, the source wins.

Deeper docs (generated + hand-written): `docs/sdk-api/` (TypeDoc reference),
`docs/sdk-guides/` (six bilingual recipes incl. "Bulletproof turn-based duel"
— the reliability contract as a tutorial), `docs/sdk-versioning-policy.md`
(what's public API + the injected-bundle back-compat rule), and
`docs/sdk-handoff.md` (architecture orientation).

## Contents

1. [Lifecycle & config](#lifecycle--config)
2. [User](#user) · [Wallet](#wallet) · [Session](#session)
3. [Storage (device-local)](#storage-device-local) · [File storage](#file-storage) · [Cloud KV](#cloud-kv-server-persisted)
4. [Game (multiplayer)](#game-multiplayer) · [Errors & diagnostics](#errors--diagnostics)
5. [Lobby](#lobby) · [Matchmaking](#matchmaking) · [Leaderboard](#leaderboard)
6. [Chat](#chat) · [Bot](#bot)
7. [Results, sharing, misc root methods](#results-sharing-misc)
8. [UI utilities](#ui-utilities)
9. [Backend channel & allowlist](#backend-channel)
10. [APIs that DO NOT exist](#apis-that-do-not-exist)

## Lifecycle & config

```javascript
Usion.init(callback)   // callback(config) — fires once config arrives from host
Usion.version          // SDK version string
Usion.config           // read-only current config
```

`config` fields: `userId, userName, userAvatar, authToken, sessionId,
sessionData, balance, results, theme ('light'|'dark'), language, socketUrl,
webTransportUrl, roomId, playerIds, serviceId, serviceName, apiUrl,
connectionMode ('platform'|'direct')`.

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
Usion.wallet.hasCredits(amount)                 // Promise<boolean>
Usion.wallet.requestPayment(amount, reason, data?)
// → Promise<{success, newBalance?, receiptToken?, transactionId?}>
// Host shows a confirmation dialog; rejects on decline or 60s timeout.
Usion.wallet.onBalanceChange(cb)                // cb(balance)
```

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
Usion.game.connectDirect({roomId?, serviceId?, apiUrl?, token?})  // force direct-mode WS
```

### Sending

```javascript
Usion.game.action(type, data?, opts?)  // Promise<{success, sequence?}> — sequenced + stored; turn-based moves
//   opts.nextTurn: playerId whose turn comes next — server remembers it and
//     returns it as current_turn on join/sync, so turn survives reconnects.
//   opts.queueOffline: hold this move while disconnected and send it (in order)
//     after recovery instead of rejecting NOT_CONNECTED. Turn-based only;
//     cap 20 then QUEUE_FULL. Never queue realtime-style inputs.
Usion.game.realtime(type, data?)  // fire-and-forget — per-frame state, positions, effects
Usion.game.setState(state)        // Promise<{success, code?}> — AUTHORITY only (playerIds[0]):
//     checkpoint authoritative state (≤64 KB); rejoining clients get it as
//     game_state in the join ack and onSync. Checkpoint at meaningful transitions.
Usion.game.requestSync(lastSeq?)  // ask server for full state → onSync
Usion.game.requestRematch()
Usion.game.forfeit()              // Promise<{success}>
```

**Reliability contract** (what generated/3rd-party games rely on — see
`docs/sdk-guides/02-bulletproof-turn-based.md`): apply moves ONLY on the
`onAction` echo (every action echoes to the sender with its authoritative
sequence; the SDK dedups by sequence, so exactly-once even across reconnect
replays) — never optimistically on send. Pass `{ nextTurn }` and trust
`current_turn` from join/sync rather than deriving the turn locally. The
authority checkpoints via `setState`. Handle `onDisconnect`/`onReconnect`/
`onPlayerConnection`.

### Handlers

Every `onX(cb)` keeps "single handler, last one wins" for back-compat but now
**returns an unsubscribe function**. For multiple listeners use
`game.on(event, cb)` — any number of listeners, works before `connect()` in
every transport, also returns an unsubscribe fn. Accepts internal names
(`'action'`), wire names (`'game:action'`), or snake_case (`'player_joined'`).

```javascript
const off = Usion.game.onAction(cb); // ...later: off();
Usion.game.on('player_joined', cb);  // additional listener, returns unsubscribe

Usion.game.onJoined(d)           // local join confirmed
Usion.game.onPlayerJoined(d)     // d.player_id, d.player_ids (full updated roster)
Usion.game.onPlayerLeft(d)       // d.player_id
Usion.game.onStateUpdate(d)      // d.game_state, d.current_turn, d.sequence
Usion.game.onSync(d)             // d.actions[], d.game_state, d.current_turn, d.sequence
Usion.game.onAction(m)           // m.player_id, m.action_type, m.action_data, m.sequence, m.current_turn?
Usion.game.onRealtime(m)         // m.player_id, m.action_type, m.action_data
Usion.game.onGameFinished(d)     // d.winner_ids[], d.reason?, d.forfeiter?
Usion.game.onGameRestarted(d)    // rematch; sequence resets to 0
Usion.game.onRematchRequest(d)
Usion.game.onError(d)            // d.message, d.code?
Usion.game.onDisconnect(reason) / onReconnect(attempt) / onConnectionError(err)
Usion.game.onPlayerConnection(d) // d.player_id, d.state: 'connected'|'reconnecting'|'gone'
//   — peer connection lifecycle: 'reconnecting' during the ~15s grace window,
//     'gone' if they don't return. Use it to pause/show "opponent reconnecting".
```

### State persistence (iframe remount recovery)

```javascript
Usion.game.saveState(state)  // localStorage keyed by player+room → boolean
Usion.game.loadState()       // T|null
Usion.game.clearState()
Usion.game.debug(payload)    // host overlay when page has ?debug=1
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
```

## Errors & diagnostics

Branch on `err.code` (stable, part of the public API), never on message text.

```javascript
Usion.ERROR_CODES   // { NOT_CONNECTED, NO_ROOM, ROOM_NOT_FOUND, NOT_PARTICIPANT,
                    //   NOT_AUTHORITY, NOT_AUTHENTICATED, JOIN_TIMEOUT, CONNECT_TIMEOUT,
                    //   STATE_TOO_LARGE, INVALID_STATE, INVALID_NEXT_TURN, RATE_LIMITED,
                    //   REQUEST_TIMEOUT, QUEUE_FULL, UNSUPPORTED, UNKNOWN }
Usion.UsionError    // class; err.code is one of the above, err.name === 'UsionError'

try { await Usion.game.setState(huge); }
catch (e) { if (e.code === Usion.ERROR_CODES.STATE_TOO_LARGE) trimAndRetry(); }

Usion.diagnostics()  // { version, transport:'socket'|'proxy'|'direct'|'none',
                     //   connected, joined, roomId, playerId, lastSequence,
                     //   lastActionApplied, rejoining }
// Auto-attached to game.debug() payloads as _diag; surfaced in the ?debug=1 overlay.
```

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
Usion.matchmaking.find(serviceId?, {size?})  // Promise<{roomId, players[]}> — size default 2
Usion.matchmaking.cancel()
Usion.matchmaking.onMatch(cb)
```

## Leaderboard

Opt-in per service (`leaderboard.enabled: true` in service config; `lb:*`).

```javascript
Usion.leaderboard.submit(score, metadata?)  // Promise<{success, score, best, rank, updated}>
Usion.leaderboard.top({limit?})             // Promise<entries[]> — global, default 20
Usion.leaderboard.friends({limit?})         // people you've messaged + you
Usion.leaderboard.me()                      // Promise<{score, rank, total}>
// entry: {user_id, name?, avatar?, score, rank, is_me, metadata?}
```

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
Usion.on(type, cb)                   // custom postMessage events from host (NOT socket events)
Usion.getTheme()                     // 'light'|'dark'
Usion.getLanguage()                  // e.g. 'en', 'mn'
Usion.claimBackButton(cb) / Usion.releaseBackButton()
```

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
(standalone) or the host's authenticated socket (embedded). Embedded mode only
allows these prefixes: **`lobby:*`, `mm:*`, `lb:*`, `kv:*`**. A new prefix
requires editing `BACKEND_EMIT_ALLOWED` in BOTH
`web/app/(main)/chat/iframe/[id]/game-handlers.ts` and
`mobile/features/iframe/message-handler.ts`, plus a backend
`register_*_handlers()` in `backend/realtime/` — and the mobile allowlist only
ships with the next EAS app release. Don't add prefixes casually.

## APIs that DO NOT exist

Common hallucinations the platform's quality checker flags as
`fictional_sdk_call`:

- `Usion.ready` → use `Usion.init(cb)`
- `Usion.user.info` → use `Usion.user.getId()/getName()/getAvatar()`
- `Usion.game.emit` → use `Usion.game.action()` or `Usion.game.realtime()`
- `Usion.on(...)` for socket events in embedded mode → it only receives host
  postMessages; use `Usion.game.on*` handlers instead.
