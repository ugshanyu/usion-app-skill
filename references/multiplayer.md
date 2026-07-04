# Multiplayer games on Usion

The platform owns rooms, matchmaking, invites (`game_invite` chat flow), and
the transport. Your game owns the rules, the simulation, and the rendering.
Never rebuild room codes, invite/share UIs, matchmaking UIs, or wager pickers.

An in-game **waiting room (lobby) is allowed** — optional, and in-room only:
while the invited players trickle into `config.roomId` a game MAY show who's
present, a ready toggle, and a host-start button. The reference pattern (from
the «13» card game): keep a `presentIds` set + `ready` map fed by
`onPlayerJoined`/`onPlayerLeft` and a `player_info` realtime broadcast; order
seats by the `config.playerIds` roster; when the HOST starts, it locks the seat
order into its first stored `action` (the deal/start), so every client — and
every reconnect — derives identical seating. What a lobby must never do:
create/switch rooms, draw invite/share affordances (the host's Share button and
`Usion.game.invite()` own that), or gate a simple 2-player duel that should
just start when both players have joined.

## The contract

0. **Know your mode (SDK ≥ 2.18).** `Usion.getLaunchParams().mode` is
   `'multiplayer'` when opened from a chat game invite, `'single'` when opened
   solo from Explore / the Game hub (`Usion.game.isMultiplayer()` is the
   boolean). A game that supports both should branch on it — run the
   host-authoritative flow below only when multiplayer; play locally when
   single. The host sets `mode` authoritatively, so trust it rather than
   inferring from `roomId` (a single-player game may still get an auto room).
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
