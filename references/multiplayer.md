# Multiplayer games on Usion

The platform owns rooms, matchmaking, invites (`game_invite` chat flow), and
the transport. Your game owns the rules, the simulation, and the rendering.
Never rebuild room codes, invite/share UIs, matchmaking UIs, or wager pickers.

## The required shape of a Usion game (read this first)

A game is opened from two completely different places, and the platform expects
two completely different behaviours. Getting this wrong is the single most
common reason a game feels broken.

| Opened from | `getLaunchParams().mode` | Your game MUST |
|---|---|---|
| **GameTok / Explore** (browse feed, tap to play) | `'single'` | Start playing **immediately** — solo or vs bots. Zero taps: no menu, no difficulty picker, no waiting room, no "Play" button. |
| **A chat game invite** (friend tapped the invite card) | `'multiplayer'` | Open the **waiting hall**: who's here, a READY toggle, host presses Start. |
| A solo session **promoted** by the host's Share button | stays `'single'`; `onRoomAssigned` fires | Tear down the solo/bot round and open the **waiting hall** as host. |

Decide it from the launch MODE, never from `roomId` — a solo launch can still be
handed an auto-created `standalone_*` room for SDK plumbing, and games that
guessed from `roomId` stranded solo players forever on "waiting for opponent":

**The whole of this document is implemented, working, in one small open-source
game: «13» (Mongol Poker) — https://github.com/nelsuh/13 (MIT, three files, no
build step; live at https://13-phi-ten.vercel.app). When a rule below is
unclear, read how «13» does it.**

```javascript
// Exactly this helper is used by the platform reference games («13», Table
// Soccer, Ludo, Mini Golf, Plane Battle).
function launchedSolo(config) {
  try {
    var lp = (window.Usion && Usion.getLaunchParams && Usion.getLaunchParams()) || {};
    if (lp.mode === "single") return true;
    if (lp.mode === "multiplayer") return false;
    if (Usion.game && typeof Usion.game.isMultiplayer === "function") return !Usion.game.isMultiplayer();
    var rid = config && config.roomId ? String(config.roomId) : "";
    return !rid || /^standalone[_-]/i.test(rid);   // older SDK fallback
  } catch (_) { return false; }
}

Usion.init(async function (config) {
  myId = config.userId;
  if (config.playerIds) roomPlayerIds = config.playerIds.slice();
  // Registered UP FRONT regardless of mode — a solo round can be promoted later.
  if (Usion.game.onRoomAssigned) Usion.game.onRoomAssigned(() => onRoomPromoted());

  if (!launchedSolo(config) && config.roomId) {
    showWaitingHall();                  // invite path → gather + ready up
    await setupMultiplayer(config.roomId);   // connect() → register handlers → join()
  } else {
    startBotsGame();                    // GameTok path → instant play, no menu
  }
});
```

`onRoomPromoted()` must stop every local timer from the bot round, reset
`ready`/present state, and show the waiting hall — the SDK has already updated
`roomId`/`mode` and is joining you as host; `onJoined` lands right after.

## The waiting hall (required for every multiplayer game)

While invited players trickle into `config.roomId`, a multiplayer game shows a
waiting hall — this is the room the invite card leads to, and it is **required**,
including for 2-player duels (a duel that auto-starts the instant the second
socket connects starts while the invitee is still reading the screen).

It must:

- **List everyone present** — avatar + name, in `config.playerIds` roster order,
  with the host tagged. Feed it from a `presentIds` set updated by
  `onJoined`/`onPlayerJoined`/`onPlayerLeft`, plus a `player_info` **realtime**
  broadcast carrying `{name, avatar, ready}` (send yours on join, on every
  join event, and on every ready toggle — late joiners missed the earlier ones).
- **Have a READY toggle per player**, mirrored to everyone.
- **Let only the host start**, and only once every present player is ready
  (min 2). The Start button is disabled otherwise; non-hosts see
  "waiting for the host to start…".
- **Lock the seat order into the first stored `action`** of the match (the
  deal/kickoff), built from *present + ready* players in roster order. That one
  action is what makes every client — and every later reconnect — derive
  identical seating. Never let each client decide seats locally.
- **Offer an escape hatch**: a "play with bots" button so a player whose friend
  never shows up isn't trapped, and an invite button that calls
  `Usion.game.invite()` (the platform picker) when more players are needed.

It must NEVER: create or switch rooms, show a room code, draw its own
invite/share picker, or show matchmaking/wager UI — the platform owns all of
that.

## In-game chat: quick phrases + free text (required)

Players sitting in the same room want to talk without leaving the game. Every
multiplayer game ships both halves (Table Soccer is the reference):

- **Quick chat** — a small tap-to-send list of canned phrases (~6–10, localized
  with the rest of your strings, trash talk included). This is the primary
  path: it's one tap, needs no keyboard, and works while a match is live.
- **Custom chat** — a "type your own" input reachable from the same picker,
  with a back button to the phrase list. Same send path, same bubble.

It rides the room relay, not the platform chat:

```javascript
const MAX_CHAT_LENGTH = 60;
function normalizeChatMessage(v) {
  if (typeof v !== "string") return "";
  const m = v.trim().replace(/\s+/g, " ");
  return m && m.length <= MAX_CHAT_LENGTH ? m : "";
}
function sendChat(value) {
  const phrase = normalizeChatMessage(value);
  if (!phrase) return false;
  if (Date.now() - lastChatAt < 700) return false;    // rate limit — spam guard
  lastChatAt = Date.now();
  showChatBubble(myId, phrase);                        // instant local feedback
  Usion.game.realtime("quick_chat", { phrase });       // fire-and-forget
  return true;
}
Usion.game.onRealtime((m) => {
  if (m.action_type === "quick_chat" && m.player_id !== myId) {
    showChatBubble(m.player_id, m.action_data && m.action_data.phrase);
  }
});
```

Rules:

- **`Usion.game.realtime`, never `Usion.chat.sendMessage`** — game chat belongs
  to the room, not to the players' conversation. It is transient by design: no
  history, no storage, and it must never ride `action()` (chat is not state and
  must not replay on reconnect).
- **Render received text as text.** `element.textContent = phrase` — never
  `innerHTML`. Re-normalize on receive; a peer can send anything.
- **Rate-limit** (~700 ms) and cap length on send AND receive.
- **Ephemeral bubbles** anchored to the sender's seat/avatar, auto-dismissing
  after ~2 s, so chat never blocks the board or steals a turn.
- **Hide the affordance when there's nobody to talk to** — solo/bot rounds and
  the pre-join state. Show it once ≥2 real players are in the room.
- Keep it reachable during play (a small toggle), dismissible with Escape /
  outside tap, and never covering the active play area.

## The contract

0. **Know your mode (SDK ≥ 2.18)** — see "The required shape" above.
   `getLaunchParams().mode` is `'multiplayer'` (chat invite → waiting hall) or
   `'single'` (GameTok / Explore → instant solo-or-bots round);
   `Usion.game.isMultiplayer()` is the boolean. The host sets `mode`
   authoritatively — never infer it from `roomId`.
1. The game opens with `config.roomId` and `config.playerIds` already set by
   the platform (from an invite or matchmaking).
2. `await Usion.game.connect()` → `await Usion.game.join(config.roomId)`.
3. **Register `onPlayerJoined`, `onPlayerLeft`, `onJoined`, and
   `onRealtime`/`onAction` handlers UP FRONT** — before or immediately after
   joining, and *even when the launch `mode === 'single'`*. Don't gate
   multiplayer setup behind `isMultiplayer()`/`mode`: a solo launch can be
   promoted to host mid-session (see "Solo → host promotion" below).
4. **`config.playerIds[0]` is the host** — the single authority.

**Solo → host promotion (SDK ≥ 2.20).** A game launched solo (`mode: 'single'`,
from Explore) can become a live multiplayer room AFTER launch — when the user
taps the host's top-bar **Share** button and sends an invite. The host posts the
room into the iframe and the SDK updates `getLaunchParams().roomId` + `.mode`
(now `'multiplayer'`), then auto-`connect()`+`join()`s it; the caller becomes the
host (`playerIds[0]`). Handle it by flipping your solo view into the
hosting/multiplayer view:

```javascript
Usion.game.onRoomAssigned(({ roomId }) => {
  // SDK already updated mode/roomId and is joining; onJoined fires right after.
  startMultiplayer();   // swap solo UI → hosting UI; you are playerIds[0]
});
```

Because of this, a multiplayer-capable game must NOT branch its whole setup on
`mode` at launch — register the multiplayer handlers regardless, and use
`onRoomAssigned`/`onJoined` to switch from the solo view into the hosting view.
`getLaunchParams().mode` stays `'single'` as the LAUNCH value; only `roomId`
flips once promoted.

**Invite friends from inside the game (SDK ≥ 2.19).** Call
`await Usion.game.invite()` to open the host's friend/group picker (recent chats
+ username search + your groups, multi-select). Everyone picked gets a game-invite
card in their chat; anyone who taps it joins THIS room and your `onPlayerJoined`
fires. It works even if the game was launched solo — the host creates a room with
the caller as host and `invite()` joins them to it — so register `onPlayerJoined`
before/right after calling it. Capacity is bounded by the game's `max_players`.
Don't build your own invite/share UI; this is the platform's.

The host ALSO surfaces a top-bar **Share** button on every game (same picker),
which is how a solo launch gets promoted — the user shares from there and your
game receives `onRoomAssigned` (above). So whether the invite originates from
`Usion.game.invite()` or the host's Share button, the platform owns it; never
draw your own Share/invite affordance. (A Call button appears in that same
top-bar slot only while in a call with invited players.)

The publish pipeline detects multiplayer from the built code: it must contain
`Usion.game.join` + `realtime`/`action` + `onPlayerJoined`/`onRealtime` calls,
or the service won't get the `multiplayer` tag and realtime config, and the
quality checker flags `mp_missing_join` / `mp_missing_sync` /
`mp_missing_peer_events`.

## Host-authoritative pattern (the default — use this)

```javascript
Usion.init(async (config) => {
  const myId = Usion.user.getId();
  const isHost = config.playerIds[0] === myId;

  await Usion.game.connect();
  await Usion.game.join(config.roomId);

  if (isHost) {
    // Host steps the simulation and broadcasts full state
    Usion.game.onRealtime((m) => {
      if (m.action_type === 'input') applyInput(m.player_id, m.action_data);
    });
    setInterval(() => {
      step(world);
      Usion.game.realtime('state', world);
      if (world.winner) Usion.game.realtime('gameover', { winner_id: world.winner });
    }, 50); // 20 Hz
  } else {
    // Guest sends inputs, renders authoritative state
    Usion.game.onRealtime((m) => {
      if (m.action_type === 'state') render(m.action_data);
      if (m.action_type === 'gameover') showResult(m.action_data.winner_id);
    });
    onLocalInput((input) => Usion.game.realtime('input', input));
  }

  Usion.game.onPlayerLeft(() => declareWinByForfeit());
});
```

Rules:
- Render BOTH (all) players.
- Winner is decided on the host and broadcast — never trust a peer's
  self-reported score, especially for paid outcomes.
- **Report the result at match end** (1-on-1): once the host decides the
  outcome, call `Usion.game.reportResult({ winnerId, scores?, displayScore? })`
  from the host only. The platform then drops a result card into the two
  players' DM ("You beat Bob — 3 : 1" / "Bob beat you — 1 : 3"). Gate it like
  your stat recording so it fires exactly once, and pass an EXPLICIT `winnerId`
  (the platform never infers the winner from the scores). See sdk-reference.md →
  "Match result cards".
- **Submit to the leaderboard too** — `reportResult()` tells the two players how
  THIS match went; `Usion.leaderboard.submit(...)` is what puts the game in
  Game Center and fires "«Name» beat your record". A multiplayer game with no
  natural score submits its cumulative wins. Both are required; neither
  replaces the other.
- `action()` = sequenced + stored, use for turn-based moves (chess, tic-tac-toe).
  `realtime()` = fire-and-forget, use for per-frame state (positions, effects).
- Handle disconnects per the "Reconnect contract" section below: pause on
  `onDisconnect`, resume on `onReconnected`; `onPlayerLeft` → forfeit win.
- Persist across iframe remounts with `Usion.game.saveState/loadState` (device-local).
- For server-side recovery, any participant can checkpoint authoritative state
  with `Usion.game.setState(state)` (≤64 KB; not host-only — keeps the snapshot
  fresh even while the host is backgrounded) — (re)joining clients receive it as
  `game_state` in the join ack and in `game:sync`, so recovery is "load
  checkpoint + replay tail" instead of replaying every action.
- Failures are never silent (SDK ≥ 2.22): every error has a stable `err.code`,
  and `realtime()` errors surface via `onError`.

## Turn-based pattern

Use `action()` and `onAction` instead of the realtime loop:

```javascript
await Usion.game.action('move', { cell: 4 });   // sequenced, stored
Usion.game.onAction((m) => applyMove(m.player_id, m.action_data, m.sequence));
Usion.game.onSync((d) => rebuildFrom(d.actions, d.game_state)); // reconnect recovery
```

### Who moves first is RANDOM — never the host (required)

The host is just `playerIds[0]`: the person who happened to send the invite.
Giving that seat the opening move hands the inviter a permanent structural
advantage, every match, in a game they chose. Decide the starter from chance
instead, and derive it so every client agrees without a negotiation round:

- **Derive it from the shared seed in the match's first stored `action`.** The
  host already broadcasts one kickoff action (deal/start) carrying the seed and
  the locked seat order; every client runs the same pure function on it, so the
  starter is identical everywhere and identical again after any reconnect
  replay. «13» does this by dealing from the seed and letting whoever holds the
  lowest card lead — chance decides, and the deal proves it.
- A plain `starter = seededRandomInt(seed, playerIds.length)` is fine when your
  game has no natural "who deals" rule. What matters is that it comes from the
  seed, not from the roster position and not from `Math.random()` on one client.
- **Rotate on rematch.** A rematch re-uses the same room and roster, so re-roll
  the seed (or pass the lead to the previous round's loser/winner by an
  explicit rule) — never let the same seat open every round of a session.
- Announce it: "«Name» goes first" on the first screen after the waiting hall,
  so the order reads as a fair roll rather than something the game did quietly.

### Every turn-based game needs a grace clock (required)

A phone that locks runs **no JavaScript**. Without a clock, one player putting
their phone in their pocket freezes the table for everyone, forever. Ship all
four pieces:

1. **A per-turn deadline, not a countdown.** Store `turnDeadline = Date.now() +
   TURN_SECONDS * 1000` and derive the displayed seconds from it every tick. A
   tick-counting timer silently gains whatever time the WebView was suspended,
   so a player could dodge their turn forever by backgrounding the app. On
   resume just re-attach the interval — the deadline already moved on. Send the
   deadline with the move (`action('move', {...})` → next turn's deadline) so
   every client shows the same clock.
2. **Freeze the clock while YOUR link is down, and give the time back.** On
   `onDisconnect` stop the timer and remember `pausedAt`; on `onReconnected`
   push `turnDeadline += Date.now() - pausedAt` and resume. A player must never
   be auto-passed for seconds they could not play through. (Backgrounded but
   still connected does NOT earn extra time.)
3. **Timeout resolution with a proxy fallback.** The active player's own client
   resolves its timeout first (auto-move / auto-pass). If that client is asleep
   it can't, so after a further grace window (~10 s) a **single deterministic
   client** — elected as "lowest-ranked present player that isn't the stalled
   seat" — plays the forced move on their behalf and flags it (`auto: true`).
   Electing exactly one prevents peers from forging each other's moves. A client
   that did not witness the turn start (it just rebuilt from a sync) waits one
   extra turn length before proxying.
4. **A forfeit grace window on departure** (~20 s). Never fold a player the
   moment `onPlayerLeft` fires — show "player left, waiting for them to
   rejoin… (Ns)" and cancel the countdown if they rejoin. `onPlayerConnection`
   `'reconnecting'` is NOT a forfeit; only `'gone'`/expired grace is. Track
   pending departures per player id — more than one can drop inside one window.

Real-time games need the same idea in a different shape: pause the simulation
and show a "Reconnecting…" overlay driven by `onConnectionState`, and only
declare a forfeit after the grace window.

## Smoothness: 2+ players must never lag or glitch

A game that plays perfectly solo and stutters with two players is failing the
platform bar. The rules that keep relayed multiplayer smooth:

- **Right channel for the job.** `realtime()` for anything per-frame
  (positions, aim, physics snapshots) — fire-and-forget, never stored.
  `action()` for turns and anything that must survive a reconnect — sequenced
  and stored. Sending per-frame updates through `action()` floods the action
  log, and rebuilding it on reconnect takes seconds.
- **Fixed broadcast rate, decoupled from rendering.** The host steps the sim and
  broadcasts at **15–20 Hz** on a timer; every client renders at 60 fps from
  `requestAnimationFrame`. Never emit once per rendered frame, and never render
  only when a packet arrives — that is exactly what "glitchy" looks like.
- **Interpolate, don't snap.** Guests buffer snapshots and render ~100 ms in the
  past with `Usion.game.createInterpolation`, or use
  `Usion.game.replicate`/`replica` which does the delta-sync + interpolation for
  you. Snapping remote entities straight to the last packet produces the
  teleporting that players read as lag. For the local player use
  `createPredictor` so your own input is instant.
- **Small, capped payloads.** Send only what changed, round floats to 1–2
  decimals, and cap input sends (a drag/pointermove listener that emits per
  event will emit 120×/s). One state object per tick beats twenty tiny messages.
- **Apply exactly once, idempotently.** Apply moves ONLY in `onAction`/
  `onRealtime` — never optimistically on send *and* again on echo (that
  double-applies and desyncs the boards). Dedupe by the authoritative
  `sequence`; make every apply function safe to re-run after a resync.
- **Never trust wall-clock comparisons across devices.** Phone clocks skew by
  seconds; use the server-issued `sequence` to decide which state is newer.
- **Keep the main thread free.** No per-frame DOM rebuilds, no layout thrash, no
  synchronous work in the socket handler — buffer and drain on the next frame.
  Pause the simulation while hidden and resync on return.
- **Prove it under a bad network before shipping:**
  `Usion.game.simulateNetwork({ latencyMs: 150, jitterMs: 60, lossPct: 5 })`.

## Reconnect contract (what the platform does on every disconnect)

Every session disconnects at least once (backgrounded app, network handoff).
The SDK handles recovery; your job is to stay idempotent and gate input:

- **Auto-recovery.** On reconnect the SDK rejoins the room and resyncs from the
  last seen sequence. Actions sent during that window **queue until rejoin +
  sync completes** — a stale move can't go out first. If the server reports a
  detached socket (`NOT_IN_ROOM` on action/realtime), the SDK auto-rejoins,
  resyncs, and retries the move once. You never call reconnect yourself.
- **Exactly-once actions.** Every `action()` is echoed with an authoritative
  `sequence`; the SDK dedupes, so `onAction` sees each move exactly once even
  across echoes and reconnect replays. Apply moves ONLY in `onAction`.
- **Connection-state machine (SDK ≥ 2.21).** `Usion.game.onConnectionState(cb)`
  (`connected → disconnected → rejoining → reconnected → connected`) drives the
  "Reconnecting…" overlay + input lock; `getConnectionState()` reads it
  synchronously. `onReconnected(cb)` fires once per reconnect AFTER the resync,
  with `{ state, lastSequence, viaSync }` — restore local state there.
- **Checkpoints are CAS-versioned (SDK ≥ 2.22).** `setState` carries the
  sequence it reflects; an older checkpoint is rejected with
  `{success:false, code:'STALE_STATE'}` → you are behind: call
  `Usion.game.requestSync()`, never retry the write.
- **`Usion.game.syncedState(initial, opts)` (SDK ≥ 2.21) is the recommended
  reconnect-safe shared state**: commits are sequenced actions applied through
  your pure `reduce` on every client in the same order; the authority
  (`player_ids[0]` by default) auto-checkpoints, and rejoiners recover
  automatically (checkpoint + tail replay + gap-fill). Use it before
  hand-rolling `setState`/`onSync` recovery.

  ```javascript
  const match = Usion.game.syncedState({ tally: {} }, {
    reduce: (s, a) => a.type === 'point'
      ? { tally: { ...s.tally, [a.playerId]: (s.tally[a.playerId] || 0) + 1 } }
      : s,
  });
  match.onChange((s) => renderScore(s.tally));
  match.commit('point', {});   // applied exactly once, on every client
  ```
- **Offline queue (turn-based ONLY).** `action(type, data, { queueOffline: true })`
  holds a move while disconnected and flushes in order after rejoin+sync. Cap
  20 (then rejects `QUEUE_FULL`). Never queue realtime inputs.
- **Peers see states, not verdicts.** `onPlayerConnection` reports
  `'reconnecting'` (grace window ~15 s — NOT a forfeit), then `'connected'` or
  `'gone'`. Only end the match on `'gone'`/`onPlayerLeft`. `game:player_left`
  carries `player_ids` — the authoritative remaining roster, mirroring
  `player_joined` — so reconcile membership from either event.
- **Foreground catch-up is automatic.** A backgrounded tab can miss actions
  without any disconnect; on return to visibility the SDK requests a sync
  (on mobile the host app drives it on foreground). Resyncs are deduped, so
  keep your `onSync` handler idempotent (restore-then-replay guarded by
  sequence).
- **No host migration today.** If the host (`player_ids[0]`) goes `'gone'`,
  nobody is promoted — end the match gracefully (settle result, offer exit)
  instead of leaving a frozen game.
- **Direct sockets self-heal too (SDK ≥ 2.24).** A liveness watchdog probes
  after 4 s of inbound silence and force-closes a dead direct socket at 12 s
  (`onDisconnect` fires with reason `'liveness_timeout'`), so a silent
  network drop recovers in seconds instead of waiting out a TCP timeout;
  reconnects reuse the still-valid access token (one WS dial), and input
  frames are held latest-only under send-buffer backpressure so recovery
  never bursts stale inputs. Your game still just handles
  `onDisconnect`/`onReconnect` — nothing new to wire. For a connection
  indicator use `Usion.game.getNetworkStats()` /
  `Usion.game.onNetworkQuality(cb)` instead of hand-rolled ping loops.
  The watchdog pauses while a mobile WebView is hidden and starts a fresh
  liveness window on foreground or after a blocked main thread, so background
  wall time never produces a false `liveness_timeout`.

### Recovery watchdogs the reference games ship (add these)

The SDK recovers from *events* it can see — a socket drop, a rejoin, a
`visibilitychange`. Production taught us about the failures it can't see. Every
one of these cost a real frozen match; they are cheap and silent in a healthy
game:

- **Mobile has no `visibilitychange`.** React Native WebViews do NOT fire it on
  app background/foreground, so the web-only listener never runs inside the
  Usion app. Detect the freeze from the wall clock instead: a 1 s heartbeat that
  sees a >3 s jump means your JS was suspended → resync.
- **Retry the resync until your sequence actually moves.** Right after a resume
  the host socket may still be reconnecting, so a fixed burst of
  `requestSync()` calls can all land in the dead window. Pump every ~1.2 s until
  `lastSeq` advances (or a ~60 s deadline), then stop.
- **Resync from YOUR last applied sequence** (`requestSync(lastSeq)`), not from
  0 (re-walks the whole match) and not from the host checkpoint alone (it lacks
  moves made while the host was backgrounded).
- **Watch for your own echo going missing.** If your `action()` echo hasn't come
  back after ~6 s, your UI is stuck waiting forever — request a catch-up.
  Likewise, if you're waiting on *somebody else* and nothing at all has arrived
  for ~20 s, ask for a sync. Debounce catch-ups (~5 s) so they never storm.
- **Checkpoint from whoever just acted**, not only from the host. A host-only
  `setState` goes stale the moment the host backgrounds: opponents' moves made
  in that window are missing from the snapshot and get silently lost on
  recovery. The actor always holds current state.
- **A turn/phase staleness watchdog.** When a phase change rides fire-and-forget
  `realtime` (turn advance, goal overlay), a single dropped packet leaves a
  client stuck. Re-arm a ~3.5 s check that pulls the checkpoint
  (`requestSync(lastSeq)` + a `request_state` broadcast) while the local view
  says "waiting on someone else".
- **Idempotent everything.** Resyncs are deduped but can still overlap;
  restore-then-replay must be guarded by sequence so a repeat sync is a no-op.

## Smoother netcode (when 20 Hz state-blasting isn't enough)

All helpers work over any transport. Compose as needed:

**Declarative replication (simplest):**
```javascript
// Host
const world = Usion.game.replicate({ players: [] }, { hz: 20, channel: 'world', precision: 2 });
world.state.players.push({ id: myId, x: 0, y: 0 }); // just mutate; SDK delta-syncs
// Guest
const view = Usion.game.replica({ channel: 'world', interpolate: 'x y' });
function frame() { render(view.view()); requestAnimationFrame(frame); }
```

**Snapshot interpolation** (smooth remote entities):
`createInterpolation({serverFps: 20})` → `interp.add(snapshot)` on receive,
`interp.calc('x y angle(deg)')` per render frame.

**Client-side prediction** (responsive local movement):
`createPredictor({apply, smooth: 'x y'})` → `predict(input)` locally +
`reconcile(serverState, ackedSeq)` on updates, render `view()`.

**Bandwidth**: `createSnapshotSender/Receiver` (delta + keyframes + quantize +
binary encode), or manual `diff/patch/quantize/encode/decode`.

**Deterministic lockstep** (RTS-style, inputs only): `createLockstep({playerId, players, step})`.

**P2P / lowest latency**: `createMesh` (2 peers, WebRTC, signaling rides
`game.realtime`), `createMeshNetwork` (3+ full mesh), `createWebTransport`
(HTTP/3 datagrams to a direct-mode server). Server-side fairness:
`createLagCompensator` for rewind hit-detection.

**Always test under bad networks** before shipping:
```javascript
Usion.game.simulateNetwork({ latencyMs: 150, jitterMs: 60, lossPct: 5 });
```

## Direct mode (own game server)

For server-authoritative games with their own backend (Path B microservices):
the backend issues an RS256 access token, the game calls
`Usion.game.connectDirect({...})` and talks WebSocket straight to your server —
platform validates but doesn't relay. Reference implementations:
`microservices/pong/server.js` (WebRTC + WS fallback, `RoomRuntime`),
`microservices/block-stack/server.js` (host-authoritative tick loop, 8 players),
`microservices/space-craft-v2/` (4-player server-authoritative shooter with lag
compensation), and **`ugshanyu/tilt-royale`** (2–4p tilt battle royale — the
only direct-mode reference kept as a standalone public repo, NOT in the
monorepo; its README is a full direct-mode + netcode tutorial and it shows the
clean split of a shared pure-physics module imported by both the server sim and
the client `createPredictor`). Registered with
`realtime.connection_mode: "direct"` in their seed scripts.

### Direct-mode netcode pitfalls (each of these shipped broken once — don't repeat them)

- **Never let a unicast frame consume the broadcast seq counter.** If your
  server numbers snapshots (`s`) and clients treat a gap as "resync needed",
  then join/rejoin/resync keyframes sent to ONE client must REUSE the current
  seq, not advance it — otherwise every unicast manufactures a gap for every
  OTHER client, whose resync request burns another seq, ping-ponging forever:
  remote players freeze between keyframes and jump. (Tilt Royale v1 bug;
  regression-pinned in its `test/seq.test.js`.)
- **Only stateful streams should stall on a seq gap.** If players/projectiles
  are full state on every frame, keep applying them through a gap and stall
  only delta-patched collections (e.g. dot membership) until a keyframe.
  Throttle resync requests (each one costs a full keyframe).
- **Don't extrapolate angles linearly.** The SDK interpolation blends angles
  on the shortest arc but extrapolates them linearly, so an underrun across
  the ±π wrap projects a huge fake angular velocity (arrows whip-spin).
  Interpolate `vx vy` instead and derive facing from velocity client-side.
- **Don't gate `connect()` on a rendered frame.** Phaser (and any RAF-driven
  engine) never ticks in a hidden/backgrounded WebView — if boot awaits the
  scene before connecting, the game silently never connects. Connect and
  scene-boot concurrently; let the scene render whatever state exists when it
  wakes.
- Mobile WebViews fire `visibilitychange` constantly (app switcher, keyboard,
  notification shade). If each foreground triggers a resync request, make the
  server skip the keyframe for clients that are already up to date.
- **Never construct the render engine while the WebView is 0×0.** Hosts show a
  loading state before revealing the iframe; Phaser (or any canvas engine)
  booted at that moment creates a 0×0 buffer and RESIZE never recovers — the
  canvas stays black for the whole match while data flows perfectly. Wait for
  a non-zero viewport before creating the game (gate ONLY the scene, never the
  connection) and drive scale from a `ResizeObserver` on the mount div —
  embedded WebViews don't reliably fire window `resize` when the host reveals
  the iframe. A render watchdog (frames counted per update; on-screen banner
  when zero) is what made this diagnosable remotely.
- **Send something downstream while a room idles.** Direct servers that only
  emit during rounds go silent in 'waiting'; proxy edges (Railway included)
  kill silently-downstream connections after ~60 s → waiting clients
  reconnect-loop, re-minting access tokens forever. Reply to heartbeats.
- **Gate dev conveniences on env flags AND verify in prod.** A bot-fill helper
  whose flag existed but was never checked hijacked real 2-player rooms: the
  bot filled the lone waiting player's room, the round auto-started, and the
  invited opponent arrived into a live round as a spectator.

## World rooms — massive multiplayer (SDK ≥ 2.23)

A **world room** runs continuously: players drop in and out at any time instead
of playing fixed matches. A service opts in with the `world` tag (alongside
`game`, `multiplayer`). Capacity: up to **200 players** for direct/hosted
services, **32** for platform relay (relay fan-out is O(N²)); default 100,
clamped to the transport's cap at registration.

Client flow — one new call, then everything works exactly as today:

```javascript
const { roomId, playerIds } = await Usion.game.joinWorld();  // or ({ serviceId })
await Usion.game.connect();      // platform relay: connect() + join(roomId)…
await Usion.game.join(roomId);   // …or Usion.game.connectDirect() for direct/hosted
```

- `joinWorld()` rides the `mm:*` channel (works embedded AND standalone).
  Placement order: the world you're already in → atomic backfill into a world
  with space → a fresh world. Sets `game.roomId`; rejects `MATCH_TIMEOUT`
  after 15 s.
- **`WORLD_FULL`** (stable code): `join()` on a world at `max_players` rejects
  with it. World rooms auto-admit non-members while there's space — the space
  check and roster append are one atomic update, so seats can't oversell.
- **Leaving frees the seat** for backfill: `leave()`, a heartbeat timeout
  (stale players are auto-pruned), and `forfeit()` all just remove the player —
  peers get `game:player_left` with the updated `player_ids` roster.
  **Forfeit == leave in a world**: no winners, no `game:finished` fan-out; the
  world keeps playing without the quitter.
- World rooms are born `status: "playing"` (`min_players: 1`) — never wait for
  a full roster; render whoever is in `player_ids` and expect constant churn.

### AOI for developer-run world servers (direct mode)

At world scale never broadcast full state to everyone — send each player only
what they can see. `Usion.netcode.createInterestGrid` is pure JS (no
DOM/window) and runs in your Node server:

```javascript
const grid = Usion.netcode.createInterestGrid({ cellSize: 256 }); // ≈ query radius
// each tick:
for (const e of Object.values(entities)) grid.upsert(e.id, e.x, e.y);
for (const p of players) {
  const { entered, left, visible } = grid.observe(p.id, p.x, p.y, 600);
  sendTo(p, { spawn: entered, despawn: left, state: slice(visible) });
}
grid.remove(deadId);        // entity despawned
grid.dropObserver(p.id);    // player left — free their tracking state
```

`observe()` is diffed per observer (`entered`/`left` since its previous call);
`query(x, y, radius)` is the stateless variant. Both are true circle tests.

### Hosted rooms (platform runs your server)

Register with `realtime.connection_mode: "hosted"` + `server_bundle_url`
(https; `ws_url` is platform-assigned — never set it; see
`references/publishing.md`). You ship ONE JS file; the platform rooms runtime
executes it in a sandbox and serves clients over the SDK direct-mode wire
protocol — to `Usion.game.connectDirect()` a hosted room is indistinguishable
from a server you run yourself.

The bundle contract (single file, CommonJS exports):

```javascript
module.exports = {
  config: { tickHz: 20, aoi: { radius: 600 } }, // tickHz 1–30 (default 20); aoi {radius, cellSize?} or false
  init(room) {},                    // room booted (once)
  onJoin(room, player) {},          // player {id, name} admitted
  onLeave(room, player) {},         // left / disconnected / forfeited
  onInput(room, player, input) {},  // input {type, data, channel: 'action'|'input'}
  tick(room, dt) {},                // fixed timestep; dt in SECONDS (capped at 0.25)
};
```

room API: `room.state` (your authoritative state; convention
`state.entities[id] = {x, y, ...}` — entities with numeric `x`/`y` are
AOI-sliced per observer, entities without positions are global),
`room.players` (array of player ids), `room.now` (server epoch ms),
`room.broadcast(type, data)` / `room.send(playerId, type, data)` (arrive at
clients as `{seq, event: type, data}` via `onRealtime`), and `room.end(results)`
(broadcasts `match_end`, stops the room).

What the platform provides: the tick loop, per-observer AOI snapshots, RS256
token auth, per-player input limits (≤ 60 messages/s, payload ≤ 8192 bytes),
and a watchdog (every hook capped at 1 s; 3 consecutive over-budget ticks end
the room with `server_overrun`, 5 consecutive tick throws with
`server_error`). Hook exceptions are caught and logged — a throwing
`onJoin`/`onInput` never crashes the room. The sandbox exposes JS intrinsics
only: no `require`, `process`, filesystem, or network, and `room.state`
crosses to the host as one JSON round-trip per tick — keep it
JSON-serializable and lean. `Usion.game.action()` and `.realtime()` both land
in `onInput` (`input.channel` tells them apart); a client `rematch` arrives as
`onInput` with `{type: 'rematch'}`.

The snapshot each client receives via `Usion.game.onRealtime`:

```javascript
{
  seq: 1042,          // advances ONCE per tick; unicast keyframes REUSE the current seq
  t: 1760000000000,   // server epoch ms
  entities: { ... },  // full map (aoi off) or this observer's visible slice + globals
  removed: ['dot_4'], // ids that left this observer's AOI or were deleted
  events: [],         // reserved (always [] in v1)
  you: 'user_9',      // only on per-observer (AOI) snapshots and keyframes
  keyframe: true,     // only on join/resync keyframes — reset your local entity cache
}
```

A `seq` gap therefore always means real missed ticks (the runtime already
applies the unicast-keyframe seq rule from the pitfalls above). **`'idle'` and
`'heartbeat'` are reserved event names**: the runtime sends
`state_delta {event: 'idle'}` keepalives after 20 s of silence and acks client
heartbeats with `{event: 'heartbeat'}` — ignore both in your client and never
name your own events that. Hosted world state resets when a world empties
(empty rooms are swept — v1 limitation), so persist anything durable in
`Usion.cloud`.
