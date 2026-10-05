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
3. [Storage (durable)](#storage-durable) · [File storage](#file-storage) · [Cloud KV](#cloud-kv-server-persisted)
4. [Game (multiplayer)](#game-multiplayer)
5. [Lobby](#lobby) · [Matchmaking](#matchmaking) · [Leaderboard](#leaderboard)
6. [Chat](#chat) · [Bot](#bot)
7. [Results, sharing, misc root methods](#results-sharing-misc)
8. [Hybrid tabbed services](#hybrid-tabbed-services-sdk--225)
9. [UI utilities](#ui-utilities) · [Screen capture guard](#screen-capture-guard-sdk--231)
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

**Never decide "I'm not inside Usions" from `window.parent === window`.** The
mobile app runs your app in a React Native WebView, where there is no parent
window — that check makes every signed-in phone user a logged-out guest (and
skips their language). Wait for INIT; if you add a standalone fallback timer,
let a late INIT still upgrade to the signed-in user. `window.ReactNativeWebView`
exists inside the mobile app if you need a hint.

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
  `{user_id, name, avatar, is_guest}`. Do NOT send it to `/auth/me` — user-facing
  endpoints reject iframe-scoped tokens by design. Never trust a client-claimed
  user id; verify server-side and cache briefly. Game-room REST endpoints
  (`POST /games/rooms`, `/games/rooms/{id}/join`, `GET /games/rooms/{id}`,
  matchmake) DO accept the scoped token — but only for rooms of your own
  service.

### Guest visitors (web) — design for them, they're your funnel

On the web, a **logged-out visitor can open your app from a shared link** and
should get a real taste of it before being asked to sign up. What that means
for your code:

- **Identity:** guests appear as `userId` starting with `guest_` (e.g.
  `guest_5f0c…`), name "Guest". The id is stable per browser, so per-user
  device storage keys keep working. It is NOT an account.
- **Their token is real.** Guests receive a scoped iframe token too; your
  backend verifies it through the same `/iframe/verify-token` call and gets
  `{user_id: "guest_…", name: "Guest", is_guest: true}`. So don't blanket-401
  tokenless-looking visitors — verify, branch on `is_guest`, and serve your
  **read-only / anonymous tier**: browse content, daily puzzle, solo play.
  Progress keyed by the `guest_` id is fine (anonymous, per-device); don't
  attach anything you'd regret to it (payments, cross-device state).
- **Platform writes fail with `AUTH_REQUIRED` for guests** — `lb:submit`,
  `cloud.set/incr`, multiplayer (`game.connect/join`, lobby, matchmaking),
  payments, share, invites. The host shows the visitor a login prompt at that
  moment and, for `leaderboard.submit`, replays the score after they sign in.
  Your job is only to not crash: wrap these in try/catch (you should already)
  and let solo/local modes carry the experience. Reads keep working: `lb.top`
  serves the real board, `cloud.get` returns empty, local `storage.*` works.
- **Opting out:** if your app genuinely has no guest surface, set
  `guest_access: "none"` on your service registration — logged-out visitors
  then get a login screen instead of a half-working app (paid apps and SDK v3
  apps are gated like this automatically). Default is open; prefer it — a
  playable teaser converts far better than a wall.

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
Usion.user.isAdult()    // true | false | null   (sync, SDK >=2.29)
Usion.user.getToken()   // JWT for socket connections (used internally)
Usion.user.getProfile() // Promise<{id, name, avatar, isAdult}>
```

### Age gating (`isAdult`)

The platform tells you **whether** the user is 18+ and nothing else — you never
receive a birth date or an exact age, and there is no `isOver(n)`. Age-gate on
this one bit.

`null` means unknown: a logged-out guest, or an account with no birth date on
file. `null` is falsy, so the natural gate already fails closed:

```javascript
if (!Usion.user.isAdult()) {
  showAgeGate();   // blocks minors AND unknown visitors
  return;
}
```

Do not treat `null` as "probably fine". If your app has an 18+ mode, an unknown
user gets the safe version of it.

**This check is client-side.** Anyone can edit the page. If the gate protects
something that actually matters (paid adult content, a legal requirement), your
own server must verify it: send the iframe token to
`POST /iframe/verify-token`, whose response carries the same `is_adult` flag
alongside `user_id`. Trust that, not the browser.

Nothing is asked of the user for this — it is derived from the birth date they
gave at sign-up, so there is no prompt and no permission to request.

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

### ⚠️ Settling is MANDATORY — an unsettled charge is auto-refunded

`requestPayment` is an **escrow hold**, not a completed sale. The user is
debited immediately, but the money is NOT paid to you (the creator) until your
server **settles** the receipt. If you never settle, the platform assumes the
user paid and got nothing, and **automatically refunds the full amount after
72 hours**. A mini-app that charges but never settles earns exactly zero — every
charge silently bounces back to the user three days later.

So every `receiptToken` must end in exactly one of two calls to the platform
backend (`https://mobile.mongolai.mn`). Both are unauthenticated-but-signed:
the receipt token itself is the credential (an HS256 JWT only the wallet can
mint), and both are idempotent — safe to retry:

```
POST https://mobile.mongolai.mn/wallet/receipt/settle
Content-Type: application/json
{ "receipt_token": "<receiptToken>" }
→ 200 { "outcome": "settled", "tx_id": "…", "status": "completed" }
// Work succeeded → capture the charge. ~90% is credited to the service
// creator's wallet, the platform keeps the fee. outcome may also be
// "already_settled" (retry no-op) or "already_refunded" (you were too late —
// the 72h sweeper or your own refund got there first).

POST https://mobile.mongolai.mn/wallet/receipt/refund
Content-Type: application/json
{ "receipt_token": "<receiptToken>" }
→ 200 { "outcome": "refunded", "tx_id": "…", "status": "refunded" }
// Work failed → release the hold back to the user. Never keep money for
// work you didn't deliver.
```

Optional pre-flight before spending your own provider credits (read-only, no
mutation — if this fails you owe nothing and need no refund):

```
POST https://mobile.mongolai.mn/wallet/receipt/verify-pending
{ "receipt_token": "…", "expected_service_id": "<your service id>",
  "expected_amount": 100 }
→ 200 { "valid": true, "tx_id": "…", "user_id": "…", "amount": 100, "status": "pending" }
// The expected_* fields stop a token minted for another app/amount from being
// replayed against yours. 409 = already settled/refunded.
```

**Which pattern to use:**

- **Instant delivery** (hint, unlock, power-up, extra life — anything you hand
  over the moment the promise resolves): settle **immediately**, in the same
  flow as the charge. Client passes the token to your server (or your server
  receives it however you like) and the server calls `/settle` right away.
  There is no reason to wait — waiting is how charges fall into the 72h
  refund trap.
- **Deferred/failable work** (AI generation, long jobs): charge → do the work →
  `/settle` on success, `/refund` on failure. Persist the `receiptToken` with
  the job so a crash between "work done" and "settle" can be retried — the
  endpoints are idempotent, so replaying is always safe.
- **No server at all?** Then don't use `requestPayment` — a purely client-side
  app has nowhere trustworthy to settle from, and every charge will auto-refund.
  Either add a tiny server endpoint that settles, or make the app free.

```javascript
// Client (instant-delivery pattern):
const { receiptToken } = await Usion.wallet.requestPayment(100, 'Hint', { idempotencyKey: key });
await fetch('https://YOUR-SERVER/api/purchase-hint', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ receiptToken }),
});

// YOUR server:
app.post('/api/purchase-hint', async (req, res) => {
  const r = await fetch('https://mobile.mongolai.mn/wallet/receipt/settle', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ receipt_token: req.body.receiptToken }),
  });
  const out = await r.json();
  if (out.outcome === 'settled' || out.outcome === 'already_settled') {
    return res.json({ ok: true, hint: computeHint() });   // deliver ONLY once settled
  }
  return res.status(409).json({ ok: false });             // refunded/invalid → don't deliver
});
```

Never mark the purchase delivered before `/settle` succeeds, and never settle
before you're sure you can deliver.

## Session

Ephemeral per-open state, synced to the host.

```javascript
Usion.session.getId()
Usion.session.getData(key?)              // all data or one key
Usion.session.setData(key, value)        // or setData({k1: v1, k2: v2})
Usion.session.clear()
```

## Storage (durable)

Per-user, per-service KV in the platform's non-TTL database. It survives
logout/login, reinstall, and device changes. The host keeps a best-effort
localStorage/AsyncStorage cache for offline reads and migrates pre-2.27 local
values once. A write/delete resolves only after the database acknowledges it.
Quota: 512 KB/value, 200 keys, 5 MB per user/service storage bucket.

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

// Friends-visible values (SDK ≥ 2.33.0-dev.2): you own them, your accepted
// friends read them in this app. 4 KB/value, 200 keys (one per item is fine).
Usion.cloud.friends.set/get/remove/keys(...)   // your own values
Usion.cloud.friends.list(key)  // Promise<[{userId, name, avatar, value, updatedAt}]>
```

**Friends scope** is how an app shows "what my friends picked" — answers,
statuses, a favourite, a daily pick — without a server of your own.
`list(key)` returns only the caller's accepted friends (mutual consent,
blocked users excluded), newest first, max 200; it never includes the caller,
strangers, or another app's values. Guests get `[]`. Keep values compact
(a short string or small object): every friend downloads them.

- Only write here what the user expects friends to see. For anything
  personal or sensitive (opinions, answers, health), tell the user plainly
  that friends see it and give them a way to stop sharing —
  `Usion.cloud.friends.remove(key)` takes it back immediately.
- Keep the private copy in `Usion.storage` / `Usion.cloud`; the friends value
  is a mirror, not the source of truth.
- `shared.*` is writable by every user of the app — treat shared counters as
  cosmetic, never as a trusted tally.

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
Usion.game.reportResult(result)   // 2–8 player match end → result cards (SDK ≥ 2.26)
//   result = {winnerId | draw, standings?, scores?, displayScore?, metric?}. Host-auth, call once.
//   Started in a GROUP CHAT → one ranked card in that group; otherwise → DM cards.
//   standings = finishing order, best first (SDK ≥ 2.27). See "Match result cards" under Leaderboard.
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

**Every game on Usion ships a leaderboard — this is required, not optional.**
It is how a game reaches Game Center (the platform's records hub) and how it
gets its retention loop, and it costs almost nothing: opt in on the service
config and call `submit()` on game over. The platform does the rest.

If the game has no obvious number, give it one and submit that — total wins,
best time (`order: "asc"`), highest level reached (`metric: "level"`), longest
streak, highest round survived. A game with no leaderboard never appears in
Game Center, never sends a "friend beat your record" notification, and has no
reason for a player to come back.

Service config (set at registration / publish):

```json
"leaderboard": { "enabled": true, "order": "desc", "mode": "best", "metric": "score", "max_score": 100000 }
// order: "desc" = higher is better (default) · "asc" = lower is better (time trials, golf)
// mode (optional): "best" (default) — the player's best result is kept forever ·
//   "rating" — an ELO-style ladder: EVERY submission replaces the player's
//   number, so it goes down when they lose. Rating boards are always ranked
//   highest-first (`order` is ignored) and the hub labels them "rating", not
//   "record". See "Rating boards" below.
// metric (optional): "score" (default) · "level" — for a LEVEL-based game,
//   submit the player's CURRENT level (their last state, see below) and set
//   "level"; the Game Center hub then shows "Level 42" instead of a bare number.
// max_score (optional): scores beyond this still record but never fire record
//   notifications — a plausibility guard against forged scores.
```

An **Mini App Creator build has no service config to edit** — publishing reads the
built code: calling `Usion.leaderboard.submit(...)` turns the leaderboard on,
and `<meta name="usion:leaderboard" content="asc">` in the entry HTML declares
that a lower score wins (times, strokes, moves), while
`<meta name="usion:leaderboard" content="rating">` declares an ELO-style ladder
(see "Rating boards"). Higher-wins is the default.
The config is set once at first publish and never overwritten afterwards, so a
board that is already live can't be reshuffled by a re-publish.

```javascript
Usion.leaderboard.submit(score, metadata?)  // Promise<{success, score, best, previous, rank, updated}>
Usion.leaderboard.top({limit?})             // Promise<entries[]> — global, default 20
Usion.leaderboard.friends({limit?})         // your accepted friends + you (powers Game Center)
Usion.leaderboard.me()                      // Promise<{score, rank, total}>
Usion.leaderboard.scores(userIds)           // SDK ≥2.28 — Promise<{userId: number|null}>, max 16 ids
// entry: {user_id, name?, avatar?, score, rank, is_me, metadata?}
// previous: what was on the board before this submit (null on a first submit)
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
- **Global top-5 notifications**: entering the global top 5 pings the player
  ("You're now #3 on «YourGame» globally"), and the player they knocked out of
  the top 5 gets notified too — both open your game. Also free from `submit()`.

Show BOTH boards on your game-over screen — `friends()` (who the player knows)
and `top({limit:10})` (the worldwide board to chase). A Friends/Global toggle
is the clean pattern (see the Flappy reference). This is required after a solo
run ends, on death, loss, or victory. Keep the earned run result and retry action
visible while records load. Render rank, player name/avatar, and the record's
metric; highlight `is_me`. Fetch refreshed boards after score submission settles,
and handle loading, empty friends lists, and network errors with a compact retry
state. Never replace unavailable records with fabricated players or scores.

**Recommended pattern for a score-based game** (this is what the Flappy
reference app does — see publishing.md):

```javascript
// on game over
const r = await Usion.leaderboard.submit(score);   // best kept automatically
showBest(r.best);
const friends = await Usion.leaderboard.friends();  // render the friends board
const global = await Usion.leaderboard.top({limit: 10});
renderRecordTabs({friends, global}); // rank, name, avatar, score; highlight is_me
// Production UI should catch submission/board failures independently and keep retry usable.
```

Submit only real, earned scores (the server keeps the best per player, so
submitting every run is fine). `friends()`/`top()` are safe to call anytime
after `Usion.init`.

### Level-based games: submit the player's last state

If the game is a **progression** game — levels, stages, worlds, chapters — the
number on the board is not a per-run score: it is **where the player currently
is**, i.e. their last state. Register the board with `"metric": "level"` and
`submit()` the level they are now on **every time it changes** (level cleared,
run resumed, save loaded), not only on a game-over screen — a progression game
may never show one.

```javascript
// whenever the player advances — and once on load, after restoring the save
async function syncProgress(level) {
  await Usion.leaderboard.submit(level);   // the level they are ON, not a run score
}
```

Because progress only moves forward, the default `"best"` mode already stores
exactly that last state: replaying an easy level can never knock a player back
down the board, and the hub always reads "Level 42" for where they really are.
Do NOT submit a per-run score, points, or the level count of a single session
on a `"level"` board — friends compare progress, so the value has to mean the
same thing for everyone.

### Rating boards (`mode: "rating"`, SDK ≥ 2.28)

For a **competitive game where players climb and fall** — chess, a 1v1 duel, any
ladder — register the board with `"mode": "rating"`. The stored value is then the
player's CURRENT rating, not their best ever: every `submit()` replaces it, so a
loss actually takes them back down and past the friend who beat them.

Your game computes the number; the platform stores and ranks it. Each player
submits their OWN rating — you can never write someone else's, so both clients
in a duel must submit (host-authoritative games: have each side submit after the
host announces the result).

```javascript
const START = 1200, K = 32;
const [mine, theirs] = await Promise.all([
  Usion.leaderboard.me(),
  Usion.leaderboard.scores([opponentId]),      // read the opponent's rating
]);
const my = mine.score ?? START;
const their = theirs[opponentId] ?? START;
const expected = 1 / (1 + Math.pow(10, (their - my) / 400));
const actual = won ? 1 : (draw ? 0.5 : 0);
const r = await Usion.leaderboard.submit(Math.round(my + K * (actual - expected)));
showDelta(r.best - (r.previous ?? START));     // "+18" / "−14"
```

Rules that keep a ladder honest:

- **New players start at a fixed rating** (1200 is the convention). `me().score`
  is `null` until their first submit, and `scores()` reports `null` for anyone
  not on the board — treat both as the starting rating.
- **Submit once per match, from a settled result.** A rating board has no
  "best kept" safety net: a duplicate submit is a duplicate rating change.
- **Only a rating that goes UP notifies anyone.** A drop is stored silently — it
  beat nobody.
- Pair it with `Usion.game.reportResult(...)` (below) so the match itself also
  lands in the chat it started from.

### Match result cards (`Usion.game.reportResult`, SDK ≥ 2.26)

Report the final result of a **2–8 player match** when it ends and the platform
delivers a result card with a tap-to-play button. This is the per-match companion
to the leaderboard's record-beaten notifications: use `submit()` for "best score
ever" bragging, `reportResult()` for "here's how our game just went".

**Show results inside the game too.** At match end, every client must show a
compact result screen using the authoritative final state and the roster locked
at match start. Include all players who actually played: name/avatar, placement
or outcome, meaningful score/time/metric, and a clear winner or draw. Highlight
the local player and label forfeits/disconnections when they affect the result;
keep departed participants in the final roster. Follow the game's actual ranking
and tie rules, including lower-is-better games. Do not invent scores for scoreless
games. Offer rematch through a fresh waiting/ready phase and an exit action where
the host does not already provide one. A chat result card or a lifetime leaderboard
does not replace this match result screen. Report the same authoritative outcome
once from the host with `reportResult()`. Default to participant standings and
Restart in multiplayer; omit Friends/Global boards unless explicitly requested.

**Where the card lands follows where the game was launched from** (the room's
originating chat) — you don't choose it, and you don't pass a chat id:

| Launched from | Delivery |
|---|---|
| A **group chat** | ONE ranked standings card posted into that group. Includes 1-on-1, so the group sees who beat who. |
| **Anywhere else** (GameTok, invite, matchmaking) | Cards in the **DMs**, each written from that player's own perspective. 1-on-1 → "You beat Bob — 3 : 1" / "Bob beat you — 1 : 3". 3–8 players → a standings card across the host↔guest DMs. |

Group chats are server-visible, so the group card is posted directly. Personal
chats are zero-knowledge, so DM cards ride a `game:result` socket event that each
client renders into its own local DM history.

```javascript
// Call ONCE, from the authoritative client only (config.playerIds[0] / your
// host), the moment the match ends. Pass an EXPLICIT winnerId — the platform
// never guesses the winner from the scores, so lowest-score-wins games (golf,
// "13") and games with no numeric score (elimination, race) work identically.
Usion.game.reportResult({
  winnerId: players[winnerSeat],          // required (or draw: true)
  scores: { [players[0]]: 3, [players[1]]: 1 },  // optional, keyed by userId
  displayScore: '3 - 1',                   // optional, your own score text
  metric: 'goals',                         // optional label
});
// draw:  Usion.game.reportResult({ draw: true, scores: {...} });

// 3–8 players: declare the finishing ORDER, best first (SDK ≥ 2.27).
Usion.game.reportResult({
  winnerId: order[0],
  standings: order,                        // ['alice','bob','chi','dorj']
  scores: { alice: 6, bob: 5, chi: 3, dorj: 1 },
});
```

- **Authoritative client only, once.** Gate it exactly like your stat recording
  (`gamePhase === 'ended'` etc.) so a losing peer can't fire a fake result — the
  backend also re-checks that the players really shared this room and dedupes,
  but the game should still only call it from the host.
- **`winnerId` is explicit** and must be a real participant. Omit it only with
  `draw: true`. `scores`/`displayScore` are optional decoration for the card.
- **`standings` is how you express a ranking** for 3+ players — it can NEVER be
  derived from `scores`, because a high score wins in some games and a low one
  wins in others. Ids not in the room are ignored, anyone you omit is appended,
  and the winner is always pulled to the front. Without it the card still shows
  the right winner, just with the rest in roster order.
- **Scoreless games should omit `scores`** — sending zeros renders a "0 : 0"
  line. Send scores only when the number means something (mini golf points, not
  Connect Four).
- Bot/AI seats are dropped (only real users are messaged), so a "you vs 3 bots"
  game produces no card at all.
- **Reporting a result ENDS the room.** The platform marks it `finished`, clears
  everyone's "Playing X" presence and flips the invite card in the chat from
  "Rejoin" to "View results". Players already in the room keep relaying actions
  (a rematch inside the same room still works), but the room is no longer a
  matchmaking target and new players join it through the room's own invite. So
  call it at MATCH end, not at the end of every round of a best-of-three.
- Each card is stored for 30 days as well as emitted live, so a player who was
  offline (or reconnecting) when you reported still finds it in the DM.

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
in the Usion app's settings for your app. SDK ≥ 2.17 supports `notifications`;
SDK ≥ 2.30 adds `profile_content` for native profile cards (see below).
Backend: per-user-per-service grants in `service_permissions`.

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

## Screen capture guard (SDK ≥ 2.31)

Mark a short window as **secret** — the moment your app shows something a
screenshot would ruin (a memory game's pattern, a hidden hand of cards, a
one-time code). The platform blocks the capture where the OS allows it and
reports it where it doesn't, so you react instead of being cheated silently.

```javascript
Usion.screen.protect(true)          // this screen is secret
Usion.screen.protect(false)         // it isn't any more — ALWAYS pair this
Usion.screen.onCapture(cb)          // cb({ kind: 'screenshot' }) -> unsubscribe fn
Usion.screen.support()              // sync -> { block: boolean, detect: boolean }
```

| Platform | While protected |
|---|---|
| Android app | Screenshot and screen recording **blocked** by the OS (`block: true`). `onCapture` never fires — there is nothing to report |
| iOS app | The OS gives no way to block a screenshot, so it is **detected** and `onCapture` fires (`detect: true`) |
| Web browser | Neither is possible (`{ block: false, detect: false }`) — see the honesty rule below |

### The rules that make this work

- **Protect the secret window, not your app.** Turn it on when the secret is on
  screen and off the instant it leaves. Protection that stays on blocks the
  user's screenshots of their own scores, leaderboards and share cards — which
  they rightly expect to work. Release it on every exit path (finished, failed,
  timed out, backgrounded, unmounted), not just the happy one.
- **Neutralize, never punish.** On `onCapture`, invalidate what leaked —
  re-shuffle the board, re-draw the pattern, rotate the code — and say something
  neutral ("pattern refreshed"). Do NOT end the turn, deduct points, or accuse
  the player: iOS reports AirPlay mirroring and screen recording as capture too,
  and people take accidental screenshots. An honest player must feel nothing
  worse than a small do-over.
- **Never a security control.** Web players can't be detected at all, and no
  platform can stop a second phone pointed at the screen. If your app is only
  fair *because* capture is blocked, it is already unfair on the web — fix that
  in the design (don't render the whole solution in one frame), not here.
- **Don't fake what the platform can't do.** Never substitute blur/visibility/
  keypress guessing for real detection; a false accusation is worse than a
  missed one. Use `support()` to decide your fallback design, and remember an
  older app binary correctly reports `{ block: false, detect: false }`.
- Both calls are safe no-ops standalone and on hosts that don't support them —
  guard nothing, but expect nothing either.

```javascript
// Memory game: the solution is only visible during the preview phase
function showPattern() {
  paintTargets();
  Usion.screen?.protect(true);
}
function hidePattern() {
  Usion.screen?.protect(false);   // recall board, results and leaderboard stay capturable
  clearTargets();
}
Usion.screen?.onCapture(() => {
  if (phase !== 'preview') return;     // a screenshot of the dark board is worthless
  startRoundAgain();                   // the captured pattern is now dead
  setStatus(t('patternRefreshed'));    // neutral wording, no accusation
});
```

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

## Results, file export, and sharing

```javascript
Usion.saveResult(data, {thumbnail_url?, title?, type?})  // server-persisted, Promise<SavedResult>
Usion.deleteResult(resultId)
Usion.getResults()                   // SavedResult[] from init config

Usion.share(contentType, data)       // platform share UI; external action attaches its first media item
Usion.shareFile(url, {               // SDK >= 2.29; actual file attachment to another app
  filename?, mimeType?, title?, text?
})                                   // Promise<{success, destination, cancelled?, fallback?}>
Usion.shareToStory(url, {            // SDK >= 2.32; straight onto an IG story
  filename?, mimeType?, stickerUrl?,
  backgroundTopColor?, backgroundBottomColor?
})                                   // Promise<{success, destination, fallback?}>
Usion.shareToFeed(contentType, data) // Promise<{success, postId?, shareUrl?}>
Usion.download(url, filename?, {     // SDK >= 2.29
  destination: 'auto'|'gallery'|'files',
  mimeType?, title?
})                                   // Promise<{success, destination, cancelled?}>

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

Use the host file APIs for exports—never rely on an iframe `<a download>`,
`window.open`, or direct `navigator.share`. Those bypass the native mobile host
and behave differently across browsers.

```javascript
// Attach a PDF to WhatsApp, Telegram, Mail, AirDrop, etc.
await Usion.shareFile(reportUrl, {
  filename: 'trip-report.pdf',
  mimeType: 'application/pdf',
  title: 'Share trip report'
});

// Images/videos go to the gallery in auto mode.
await Usion.download(posterUrl, 'poster.png', {
  destination: 'auto',
  mimeType: 'image/png'
});

// Documents, archives, audio, and other materials go to Files/Downloads.
const saved = await Usion.download(csvUrl, 'scores.csv', {
  destination: 'files',
  mimeType: 'text/csv'
});
if (!saved.success && saved.cancelled) return; // user closed the picker
```

File-transfer rules:

- Call `shareFile`/`download` directly from a visible user tap. OS and browser
  pickers may be blocked when opened automatically or after a long async chain.
- Pass a public `https://` URL whenever possible. Base64 `data:` URLs work up to
  10 MB for locally generated canvas/text exports. Mobile cannot read an iframe
  `blob:` URL; convert a small Blob to a data URL or upload it and pass HTTPS.
- Remote transfers are capped at 100 MB. Any file type goes through: the host
  recognizes common image, audio, video, document, archive, font, and text
  formats from the filename extension, and carries anything else as opaque
  bytes with its name intact. Still pass an explicit `filename` and `mimeType`
  when you know them — that is what decides which apps the share sheet offers.
- `destination: 'auto'` sends images/videos to the gallery and everything else
  to Files/Downloads. `gallery` rejects non-image/video MIME types. On iOS,
  arbitrary-file download opens the system sheet where the user chooses **Save
  to Files**. On Android it opens a directory picker. On web, unsupported binary
  Web Share falls back to sharing the URL or downloading the file; check
  `result.fallback` if the distinction matters.
- `Usion.shareToStory(imageUrl)` opens Instagram's story composer with your
  image already on the canvas, and carries the "Play on Usions" attribution chip
  back to the platform. It is safe to call anywhere: on the web, on an older app
  build, or when Instagram is not installed it falls back to the ordinary share
  sheet and sets `fallback: true`, so never branch on platform yourself. Images
  only — a 1080x1920 export is the right shape. The chip needs the platform's
  Facebook App ID to be configured; without it you still get the normal share.
- `Usion.share` remains the user-facing platform share flow (Usions contacts,
  service attribution, then an external action). Use `shareFile` when the button
  specifically means “send this file to another app.” Use `shareToFeed` only for
  a signed-in user's attributed Usions feed post.

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

## Minimal game UI inside Usions

Usions already provides the game identity and host header. Do not add a second
header, game name/logo, branding strip, back/share controls, or duplicate host
buttons inside the embedded game. Check which actions the host actually exposes;
keep any essential game-specific action that has no usable host equivalent.
Standalone games without a host header may provide their own compact navigation.

- Make the playable board/world the main use of the phone viewport. Fit it close
  and large in portrait and landscape, reserving only the space the controls need.
- Default to minimal text: omit slogans, welcome copy, decorative section titles,
  persistent instructions, and labels that repeat what an icon or state shows.
  Show only indicators that help the next decision (for example health, remaining
  moves, timer, ammo or a relevant face preview), not a dashboard of statistics.
- Prefer direct touch or swipes when they fully express the controls. Do not add
  a directional pad as a duplicate of working swipes. Use a joystick/buttons when
  the mechanic needs continuous movement, simultaneous actions or precise control.
- Keep primary actions clear, visually prominent, and easy to tap. For simple
  round screens, make Lock in, Next, and Restart fill the available content width;
  use compact controls for settings and secondary actions. Put detailed help/settings and nonessential statistics behind deliberate
  access instead of permanently occupying the playfield.
- Minimal visible text must retain accessible names, essential warnings, outcomes,
  score persistence and usable start/resume/retry flows. Honor explicit user choices.
- Review the game inside the actual Usions shell on a phone: no duplicated header,
  no redundant labels or controls, no cropped board, and no control/playfield overlap.

## Game flow, scoring, and result persistence

### Minimal visible text

- Start solo play immediately. Omit welcome screens, slogans, explanatory
  paragraphs, repeated game titles, and an extra Start gate.
- Put optional round count, help, and settings behind a compact top control;
  reuse the host invite picker. For a simple round game, 5 rounds with 5/10/15
  choices is a useful default, not a requirement for other mechanics.
- Prefer short labels (Ready, Start, Lock in, Next, Restart) and accessible
  names on icon buttons. Keep essential score, timer, outcome, and save failures.
- Solo finish: compact score/best, relevant result comparisons, Friends/Global
  toggle, and a prominent Restart. Fetch real records inside the game; do not
  replace them with “Open Usions to see records” copy.
- Multiplayer finish: all actual participants, meaningful points and placements,
  winner/draw, and Restart. Hide solo record boards by default. For color games,
  original/guess swatches should be small comparisons, not another large board.

### One shared multiplayer match

An invite must lead to the same waiting room and match. Show joined players and
readiness; let the host choose round count before Start. Changing the rules clears
readiness. Start once the minimum player count is met and everyone present is
ready. Support the requested capacity in both registry settings and game logic;
for suitable round games, 2–8 people can play together. Do not hardcode two seats.

Lock the actual roster and shared seed/rules at start. Use the same challenges
for everyone, validate each player's input, and derive points from authoritative
state rather than accepting claimed scores. Show live points for every player.
Round barriers wait for all required participants, with disconnect/recovery rules;
Restart returns the room to readiness with a new match identity. See
[multiplayer.md](multiplayer.md) for transport and room lifecycle details.

### Scores that players can trust

Choose a metric that fits the mechanic and label it accurately. Check exact,
near, and clearly wrong answers plus boundaries and ties. An accuracy percentage
must give a perfect match 100% and clearly unrelated answers zero, without a
positive floor. Color matching should use perceptual distance (for example OKLab)
and a calibrated cutoff/curve rather than normalized RGB distance. A game score
is not a scientific similarity percentage. Keep formulas deterministic and shared
across clients; version changed scoring metadata so old records are distinguishable.

### Save the completed result, independently of navigation

Initialize the SDK in both browser iframes and top-level React Native WebViews.
`window.parent === window` does not imply standalone: the native bridge can be
`window.ReactNativeWebView`. Wait for `Usion.init` before platform writes.

Capture the final earned result as soon as the terminal state is authoritative.
For a simultaneous final round, this is when all final guesses are locked, not
when everyone taps Next/See results. Submit solo scores via
`Usion.leaderboard.submit`; report a shared outcome from the authoritative client
via `Usion.game.reportResult`, with explicit winner/draw and standings for 3+
players. Use the documented stable match identifier across retries.

Await the documented positive backend acknowledgment; a resolved promise alone
is not proof of success. Keep small Saving/Saved/Retry states. Preserve an unsent
completed result through Restart; a later worse run must not discard a higher
unsaved best. Retry the captured result without recomputing it or creating a new
match identity. Do not attach an old device-local best to a different account.
Refresh records after successful submission; local best and remote records are
separate until the server confirms. Keep play/restart usable if records fail.

### Verify the player journey before announcing

Play solo through completion and confirm the account record is stored. Test
failed acknowledgment and retry, restart before save, and native bridge init.
Use distinct clients to verify invite → waiting room → all ready → shared rounds
→ live points → final result saved → participant results → rematch, including
maximum requested capacity and reconnect. Simulated clients are useful evidence;
do not describe them as production accounts or physical-device tests.

Inspect portrait and landscape inside the Usions shell: no duplicate header,
page overflow, clipped controls, or crowded result rows. Keep comparisons in an
internal scroll area if needed and Restart reachable. Announce only when asked,
after release verification; use one deduplicated campaign, concise title/body,
and a game deep link. Provider acceptance is not proof that every user received
an OS notification.

## UI utilities

```javascript
Usion.setLoading(btnOrSelector, loading)   // usion-btn-loading class + disable
Usion.toggle(elOrSelector, show)
Usion.charCount(input, counter, max)
Usion.selectionGrid(containerSel, itemSel, onChange)  // → {getSelected(), clear()}
```

Design tokens: `https://usions.com/usion-design-system.css`.

### A game is not a web page: kill selection, zoom and rubber-band

Mini-apps run in an iframe on web and a **WebView on mobile**, where every
default browser gesture is still live. A tap-and-hold on a game piece pops the
text-selection handles and the copy/"Look up" callout, a fast double-tap zooms
the board, a swipe rubber-bands the whole surface, and every tap flashes a grey
highlight box. It reads as a broken web page instead of a game, and it breaks
drag controls outright — the selection gesture eats the drag.

Put this in the entry HTML of **every game** (and any app with drag/tap
controls). It costs four lines and there is no case where a game wants the
defaults:

```html
<meta name="viewport"
      content="width=device-width, initial-scale=1, maximum-scale=1,
               user-scalable=no, viewport-fit=cover">
```

```css
html, body {
  height: 100%;
  overflow: hidden;                 /* no page scroll behind the game */
  overscroll-behavior: none;        /* no pull-to-refresh / rubber-band */
}
* {
  -webkit-user-select: none; user-select: none;   /* NOT selectable */
  -webkit-touch-callout: none;                    /* no long-press callout */
  -webkit-tap-highlight-color: transparent;       /* no grey tap flash */
  touch-action: manipulation;                     /* no double-tap zoom */
}
/* Text the player must be able to select or type into stays selectable. */
input, textarea, [contenteditable] { -webkit-user-select: text; user-select: text; }
```

- On the **play surface itself** (canvas or board container) use
  `touch-action: none` so a drag never turns into a scroll, and call
  `e.preventDefault()` in your `touchmove` handler (register it with
  `{passive: false}` — a passive listener cannot prevent the scroll).
- Mark images and canvases `draggable="false"`; a long-press otherwise offers
  "Save image".
- Keep it OFF for genuinely readable content — a rules screen, a chat log, a
  result the player may want to copy. Selection is a feature there.

## Backend channel

`Usion._backendEmit(event, data)` routes through the app's own socket
(standalone) or the host's authenticated socket (embedded). Standalone apps
don't need to call `Usion.game.connect()` first — the first cloud /
leaderboard / notify / lobby / matchmaking call connects automatically
(SDK ≥ 2.22). Embedded mode only
allows these prefixes: **`lobby:*`, `mm:*`, `lb:*`, `kv:*`, `notify:*`, `gc:*`**. A new prefix
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

## Profile content (SDK 2.30+)

Profile starts with **Record** (selected by default), then **Right now**, then
one category per app with content and an explicit `profile_content` grant.
The app category uses its registered name. Signed-in profile visitors can see
its cards, subject to blocking; Right now retains its existing audience rules.

Ask after a user taps a clearly labeled action such as “Show on my profile”:

```js
const consent = await Usion.permissions.request(['profile_content'], {
  reason: 'Show your artwork in this app’s category on your profile.',
});
if (consent.permissions.profile_content) {
  await Usion.profile.setContent({
    items: [{
      id: 'artwork-1',
      title: 'My latest artwork',
      description: 'Made with Drawing Studio',
      imageUrl: 'https://your-cdn.example/artwork-1.png',
    }],
  });
}
```

- `Usion.profile.getContent()` returns `{ items }` for this app and the current
  user only. Requires the grant.
- `Usion.profile.setContent({ items })` replaces this app’s complete list and
  returns the saved `{ items }`. It never requests permission automatically.
- `Usion.profile.clearContent()` removes the app’s content and resolves void.
  Cleanup is allowed after revocation too. Publishing `items: []` also hides
  the category but retains permission.
- Up to 50 cards: unique `id` (1–80 letters/digits/underscores/hyphens), `title`
  (1–120 characters), optional plain-text `description` (≤2,000), optional
  HTTPS `imageUrl` (≤2,048, no credentials). Upload images first. HTML,
  scripts, embedded frames, custom links and arbitrary extra fields are rejected.
  Card taps open the originating app in Usion.
- `PERMISSION_DENIED` means consent is missing or revoked. Check
  `Usion.permissions.has('profile_content')` without prompting, and handle
  denial gracefully. Cancellation never publishes content.
- Only a published app with a live grant and nonempty content appears on the
  profile. Revocation in Settings or “Remove from profile” hides it and prevents
  further publishing. Existing stored content can reappear if access is granted
  again; use `clearContent()` to delete it.
- This is the stable **v2** SDK API. It requires updated web/mobile hosts and
  backend. Older hosts reject after the 30-second request timeout; standalone
  pages reject with `UNSUPPORTED`. Never fall back to silently publishing.
- The host binds the signed-in user and current service. Mini-apps cannot select
  another owner or service, grant themselves access, or read Record/Right now
  data through this API. Existing leaderboard APIs continue to supply Record.
