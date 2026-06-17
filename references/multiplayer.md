# Multiplayer games on Usion

The platform owns rooms, matchmaking, invites (`game_invite` chat flow), and
the transport. Your game owns the rules, the simulation, and the rendering.
Never rebuild lobbies, ready screens, room codes, or wager pickers.

## The contract

1. The game opens with `config.roomId` and `config.playerIds` already set by
   the platform (from an invite or matchmaking).
2. `await Usion.game.connect()` → `await Usion.game.join(config.roomId)`.
3. Register `onPlayerJoined`, `onPlayerLeft`, and `onRealtime`/`onAction`
   handlers before or immediately after joining.
4. **`config.playerIds[0]` is the host** — the single authority.

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
- Handle disconnects: `onPlayerLeft` → forfeit win; `onDisconnect`/`onReconnect`
  → pause + `Usion.game.requestSync()` on recovery.
- Persist across iframe remounts with `Usion.game.saveState/loadState` (device-local).
- For server-side recovery, the host can checkpoint authoritative state with
  `Usion.game.setState(state)` (≤64 KB) — (re)joining clients receive it as
  `game_state` in the join ack and in `game:sync`, so recovery is "load
  checkpoint + replay tail" instead of replaying every action.

## Turn-based pattern

Use `action()` and `onAction` instead of the realtime loop:

```javascript
await Usion.game.action('move', { cell: 4 });   // sequenced, stored
Usion.game.onAction((m) => applyMove(m.player_id, m.action_data, m.sequence));
Usion.game.onSync((d) => rebuildFrom(d.actions, d.game_state)); // reconnect recovery
```

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
compensation). Registered with `realtime.connection_mode: "direct"` in their
seed scripts.
