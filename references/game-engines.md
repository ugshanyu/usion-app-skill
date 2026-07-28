# Game engines (platform-hosted runtimes)

Usion hosts pinned, versioned game-engine runtimes on its own origin. They are
the ONLY external scripts a mini-app may load — anything else is stripped at
deploy. Because every app references the same URLs, the engine is cached once
on the device and shared across all Usion games.

## Which engine (decision rule)

- **No engine** — apps, quizzes, cards, board/puzzle games, simple canvas
  games. Plain DOM/canvas is lighter and easier to get right. Default to this.
- **Phaser 4** — real 2D games: platformers, arcade action, shooters, anything
  wanting sprites, tweens, particles, or 2D arcade physics.
- **Babylon.js + Havok** — real 3D games: physics playgrounds, ball-rollers,
  third-person character games ("walk around a world" — Roblox-style).
- **Usion World Engine** — a shared 3D WORLD: a city with drivable cars,
  weapons, hazards and up to 200 players in one place. Use it whenever the ask
  is "GTA-like", "open world", "racing through a city", "battle royale",
  "Fall Guys", or any competition many players join at once. It brings its own
  Babylon renderer, so load Babylon with it and never Havok.

Never load an engine "just in case", and never load more than one (the world
engine plus Babylon is one choice, not two).

## Allowed script tags (copy EXACTLY)

Put the tag(s) in `<head>` BEFORE your inline app code. (The platform separately
injects the Usion SDK — never add that one yourself.)

```html
<!-- 2D games -->
<script src="https://usions.com/vendor/phaser/4.2.1/phaser.min.js"></script>

<!-- 3D games (Havok is the physics engine; its .wasm loads from the same folder) -->
<script src="https://usions.com/vendor/babylon/9.16.1/babylon.js"></script>
<script src="https://usions.com/vendor/havok/1.3.13/HavokPhysics_umd.js"></script>

<!-- Shared 3D worlds: massively-multiplayer city/vehicle/combat games -->
<script src="https://usions.com/vendor/babylon/9.16.1/babylon.js"></script>
<script src="https://usions.com/vendor/usion-world/1.0.0/usion-world.js"></script>
```

No other CDN, no other version, no other library (no three.js, no jQuery, no
Google Fonts). Assets too: never load textures/models/sounds from the web —
draw with the engine (Graphics/MeshBuilder), generate textures, or embed small
base64 assets.

## Phaser 4 (2D)

```javascript
Usion.init(function (config) {
  new Phaser.Game({
    type: Phaser.AUTO,
    parent: 'game',                    // <div id="game"></div> filling the page
    backgroundColor: '#ffffff',
    scale: { mode: Phaser.Scale.RESIZE, width: window.innerWidth, height: window.innerHeight },
    physics: { default: 'arcade', arcade: { gravity: { y: 900 } } },
    scene: { create: create, update: update },
  });
});
```

- Create the game INSIDE `Usion.init` — never before.
- No `preload` of external URLs. Make textures in `create` with
  `this.add.graphics()` (+ `generateTexture(key, w, h)`) or `this.add.rectangle/circle`.
- Input is touch-first: `this.input.on('pointerdown', ...)`, pointer position,
  or on-screen buttons. Never require a keyboard.
- Arcade physics gives you gravity/velocity/collisions:
  `this.physics.add.sprite(...)`, `this.physics.add.collider(a, b)`,
  `setVelocity`, `body.blocked.down` for "on ground" (jump gating).

## Babylon.js + Havok (3D with ready-made physics)

Boilerplate (inside `Usion.init`, callback may be `async`):

```javascript
const canvas = document.getElementById('c');            // <canvas id="c"> filling the page
const engine = new BABYLON.Engine(canvas, true, { adaptToDeviceRatio: true });
const scene = new BABYLON.Scene(engine);
let hk = null;
try { hk = await HavokPhysics(); } catch (e) {}          // fails on iOS < 16.4 (no WASM SIMD)
if (!hk) { showUnsupportedScreen(); return; }            // ALWAYS handle this path
scene.enablePhysics(new BABYLON.Vector3(0, -9.81, 0), new BABYLON.HavokPlugin(true, hk));
engine.runRenderLoop(() => scene.render());
window.addEventListener('resize', () => engine.resize());
```

Physics bodies are one line each (`mass: 0` = static):

```javascript
const ground = BABYLON.MeshBuilder.CreateGround('g', { width: 40, height: 40 }, scene);
new BABYLON.PhysicsAggregate(ground, BABYLON.PhysicsShapeType.BOX, { mass: 0 }, scene);
const ball = BABYLON.MeshBuilder.CreateSphere('b', { diameter: 1 }, scene);
new BABYLON.PhysicsAggregate(ball, BABYLON.PhysicsShapeType.SPHERE, { mass: 1, restitution: 0.6 }, scene);
```

### Ready-made character controller (walk/jump/gravity/collisions)

Use `BABYLON.PhysicsCharacterController` — do NOT hand-roll character physics:

```javascript
const capsule = BABYLON.MeshBuilder.CreateCapsule('p', { height: 1.8, radius: 0.45 }, scene);
const cc = new BABYLON.PhysicsCharacterController(
  new BABYLON.Vector3(0, 2, 0), { capsuleHeight: 1.8, capsuleRadius: 0.45 }, scene);
const up = new BABYLON.Vector3(0, 1, 0);
const gravity = new BABYLON.Vector3(0, -18, 0);
const moveInput = new BABYLON.Vector3(0, 0, 0);          // set x/z in [-1,1] from joystick
let wantJump = false;                                    // set true on jump button

scene.onBeforeRenderObservable.add(() => {
  const dt = engine.getDeltaTime() / 1000;
  if (dt <= 0) return;
  const support = cc.checkSupport(dt, new BABYLON.Vector3(0, -1, 0));
  const onGround = support.supportedState === BABYLON.CharacterSupportedState.SUPPORTED;
  const desired = new BABYLON.Vector3(moveInput.x, 0, moveInput.z).scaleInPlace(6); // 6 m/s
  const next = cc.calculateMovement(dt,
    camera.getDirection(BABYLON.Vector3.Forward()),               // facing
    onGround ? support.averageSurfaceNormal : up,
    cc.getVelocity(),
    onGround ? support.averageSurfaceVelocity : BABYLON.Vector3.ZeroReadOnly,
    desired, up);
  if (!onGround) next.addInPlace(gravity.scale(dt));              // airborne: fall
  else if (wantJump) { next.y = 9; wantJump = false; }            // grounded: jump
  cc.setVelocity(next);
  cc.integrate(dt, support, gravity);
  capsule.position.copyFrom(cc.getPosition());                    // drive the visible mesh
});
```

Camera for third-person: `new BABYLON.ArcRotateCamera('cam', -Math.PI/2, 1.1, 9, capsule.position, scene)`
+ `camera.lockedTarget = capsule` (skip `attachControl` if you drive the camera
yourself). Add one `HemisphericLight`. On-screen thumb joystick + jump button
(DOM overlay) — touch-first, never keyboard-only.

## Usion World Engine (shared 3D worlds, 100–200 players)

`UsionWorld` is a whole world in a script tag: a city you can collide with,
cars you can drive, weapons, moving hazards, touch controls, a third-person
camera, a HUD, client prediction and interpolation. The SAME simulation runs
on the server as the authority, so nobody can cheat their position and nothing
drifts.

Client — this is the complete app:

```html
<script src="https://usions.com/vendor/babylon/9.16.1/babylon.js"></script>
<script src="https://usions.com/vendor/usion-world/1.0.0/usion-world.js"></script>
<script>
Usion.init(function () {
  UsionWorld.start({
    labels: STRINGS[Usion.getLanguage()] || STRINGS.en,   // your translations
    locale: Usion.getLanguage(),
  });
});
</script>
```

`start()` joins the world (`joinWorld()` + `connectDirect()`), regenerates the
world from the seed the server sends, and runs everything. Do NOT write your
own render loop, movement code, or netcode around it.

Server — a world game needs one, and the platform can host it. Register with
`realtime.connection_mode: "hosted"` + `server_bundle_url` and ship ONE file:

```javascript
module.exports = UsionWorldEngine.createWorldBundle({
  worldSpec: { generator: 'city', options: { seed: 7, blocks: 6 } },
  mode: { id: 'race', laps: 2 },       // freeroam | deathmatch | race | elimination
});
```

A custom competition is a plain object of hooks — the physics never changes:

```javascript
const myMode = {
  id: 'tag',
  config: { respawnDelay: 3, startWeapons: ['shove'] },
  init(sim) { sim.state.mode = { phase: 'live', endsAt: sim.state.t + 180 }; },
  onDeath(sim, victim, killer) { if (killer) killer.score += 1; },
  onCheckpoint(sim, player, cp) { player.score += 5; },
  onTick(sim, dt) { /* your rules */ },
  projectState(sim) { return { phase: sim.state.mode.phase }; },  // codes, never sentences
};
```

Rules that matter:

- The world is described by a SPEC, not assets: `{generator:'city', options:{seed}}`.
  Both sides generate identical geometry — never ship or fetch a mesh.
- Tag the service `game` + `multiplayer` + `world` (drop-in/drop-out, cap 200).
- Mode state you replicate must be CODES and numbers; the client localizes.
- Never run Havok next to it: two solvers diverge and the game feels broken.
- Reference implementation: `microservices/usion-city` (live at
  usion-city-production.up.railway.app), engine: `packages/world-engine`.

## Multiplayer with an engine

The host-authoritative contract (see the multiplayer reference) does not
change: **only the host (`config.playerIds[0]`) runs the simulation/physics.**

- Host: steps physics, broadcasts compact snapshots 10–20×/s —
  `Usion.game.realtime('state', { players: { [id]: { x, y, z, ry } } })`.
- Guests: do NOT run Havok / arcade physics for shared objects. Render meshes
  and smoothly lerp them toward the latest snapshot; send inputs with
  `Usion.game.realtime('input', { dir, jump })`.
- Two physics engines stepping independently WILL diverge — never mirror the
  sim on guests and hope it matches.

## Engine pitfalls (observed — do not repeat)

- Loading any script other than the pinned URLs above — stripped at deploy,
  app breaks. Copy the tags exactly.
- Calling `HavokPhysics()` without try/catch + a friendly unsupported screen —
  hard crash on older iPhones (iOS < 16.4).
- Creating the game/engine before `Usion.init` fires.
- `setInterval` game loops — use the engine's loop
  (`scene.update` / `runRenderLoop`); pause when the page is hidden.
- Missing `engine.resize()` on window resize (Babylon) or a fixed-size Scale
  config (Phaser) — game doesn't fit the embedded frame.
- Hundreds of dynamic bodies — keep it under ~100; these run on low-end phones.
- Loading fonts/textures/models from external URLs — draw or embed instead.
