# Usion SDK — full API reference

Source of truth: `packages/sdk/src/modules/*.js` and `packages/sdk/types/index.d.ts`
(npm `@usions/sdk`, version in `packages/sdk/package.json` — 2.14.0 at time of
writing). The browser bundle is served at `https://usions.com/usion-sdk.js`.
If anything here disagrees with the source, the source wins.

## Contents

1. [Lifecycle & config](#lifecycle--config)
2. [User](#user) · [Wallet](#wallet) · [Session](#session)
3. [Storage (device-local)](#storage-device-local) · [File storage](#file-storage) · [Cloud KV](#cloud-kv-server-persisted)
4. [Game (multiplayer)](#game-multiplayer)
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
Usion.getLaunchParams() // {path, ref, roomId} — how the host opened this app
```

`config` fields: `userId, userName, userAvatar, authToken, sessionId,
sessionData, balance, results, theme ('light'|'dark'), language, socketUrl,
webTransportUrl, roomId, playerIds, serviceId, serviceName, apiUrl,
connectionMode ('platform'|'direct'), launchPath, ref`.

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
Usion.game.connectDirect({roomId?, serviceId?, apiUrl?, token?})  // force direct-mode WS
```

### Sending

```javascript
Usion.game.action(type, data?, opts?)  // Promise<{success, sequence?}> — sequenced + stored; turn-based moves
//   opts.nextTurn:     player ID whose turn is next — server remembers it and hands it to
//                      (re)joining clients as current_turn, so turn state survives reconnects
//   opts.queueOffline: hold the move while disconnected and send it (in order) on reconnect
//                      (turn-based only — never for realtime, which would replay stale inputs)
Usion.game.realtime(type, data?)  // fire-and-forget — per-frame state, positions, effects
Usion.game.requestSync(lastSeq?)  // ask server for full state → onSync
Usion.game.requestRematch()
Usion.game.forfeit()              // Promise<{success}>
```

### Handlers

```javascript
Usion.game.onJoined(d)         // local join confirmed
Usion.game.onPlayerJoined(d)   // d.player_id, d.player_ids (full updated roster)
Usion.game.onPlayerLeft(d)     // d.player_id
Usion.game.onStateUpdate(d)    // d.game_state, d.current_turn, d.sequence
Usion.game.onSync(d)           // d.actions[], d.game_state, d.sequence
Usion.game.onAction(m)         // m.player_id, m.action_type, m.action_data, m.sequence
Usion.game.onRealtime(m)       // m.player_id, m.action_type, m.action_data
Usion.game.onGameFinished(d)   // d.winner_ids[], d.reason?, d.forfeiter?
Usion.game.onGameRestarted(d)  // rematch; sequence resets to 0
Usion.game.onRematchRequest(d)
Usion.game.onError(d)          // d.message, d.code?
Usion.game.onDisconnect(reason) / onReconnect(attempt) / onConnectionError(err)
Usion.game.onPlayerConnection(d)  // a peer's connection state changed (transient drop/recover)
```

Each `onX(cb)` keeps a SINGLE handler (last registration wins) but returns an
unsubscribe function. For multiple listeners on the same event use
`Usion.game.on(event, cb)` — it supports any number of listeners, can be called
BEFORE `connect()`, works in every transport, and returns an unsubscribe
function. It accepts the internal name (`'action'`), the wire name
(`'game:action'`), or snake_case (`'player_joined'`).

### State persistence (iframe remount recovery)

```javascript
Usion.game.saveState(state)  // localStorage keyed by player+room → boolean (device-local)
Usion.game.loadState()       // T|null
Usion.game.clearState()
Usion.game.debug(payload)    // host overlay when page has ?debug=1

// Server-side authoritative checkpoint (host / playerIds[0] only, ≤64 KB).
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

### Push notifications

When a service/bot message reaches a user who is **offline**, the user now gets a
push notification showing the **service/bot name** + the **message preview** (text,
or `📷 Photo` / `🎵 Voice message` / `📍 Location` / `🎮 <game>` for media/components).
Tapping it opens the chat. No setup needed — it fires automatically on send.
Personal 1-on-1 messages stay end-to-end encrypted, so their pushes show the sender
name but a generic body ("Sent you a message"), never decrypted content.

## Notify

Let your app notify ITS OWN user — even when they aren't looking at it. Delivery
is context-aware: an in-app banner when the user is online elsewhere in Usion, an
OS push when they're offline or the app is backgrounded. Tapping reopens your app
(at `path`, if given). SDK ≥ 2.13. Backend: `backend/realtime/notify_handlers.py`.

```javascript
Usion.notify.send({ title, body, path? })  // Promise<{success, delivered}>
Usion.notify.setMuted(muted)               // user opt-out for this app
Usion.notify.isMuted()                     // Promise<boolean>
```

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
Usion.on(type, cb)                   // custom postMessage events from host (NOT socket events)
Usion.diagnostics()                  // {version, transport, connected, joined, roomId, playerId, lastSequence, ...}
                                     //   live SDK snapshot — also auto-attached to game.debug payloads
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
allows these prefixes: **`lobby:*`, `mm:*`, `lb:*`, `kv:*`, `notify:*`**. A new prefix
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
