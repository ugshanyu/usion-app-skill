# Game engines (platform-hosted runtimes)

Usion hosts pinned, versioned game-engine runtimes on its own origin. They are
the ONLY external scripts a mini-app may load — anything else is stripped at
deploy. Because every app references the same URLs, the engine is cached once
on the device and shared across all Usion games.

## Which engine (decision rule)

- **No engine** — apps, quizzes, cards, board/puzzle games, simple canvas
  games. Plain DOM/canvas is lighter and easier to get right. Default to this
  for anything that is NOT an action game.
- **Phaser 4** — real 2D games: platformers, arcade action, shooters, anything
  wanting sprites, tweens, particles, or 2D arcade physics.
- **three.js** — EVERY 3D game: racing, sports seen in perspective, flying,
  ball-rollers, runners, shooters, third-person
  walk-around worlds, 3D board/arena games. Real 3D models (GLB), lights,
  shadows and post-processing live here. three.js is the ONLY 3D engine.

If the game is 3D in the user's mind — they said "3D", or it is a car/truck
race, a first/third-person view, a ball on a court or pitch seen in
perspective — build it in 3D with three.js. Do NOT flatten it into a top-down
2D canvas because that is easier: a flat tennis or racing game reads as cheap.

Never load an engine "just in case", and never load more than one.

(Games built before 2026-11-16 may use Babylon.js + Havok from
`usions.com/vendor/babylon` and `/havok`. Those files stay hosted: when asked
to change such a game, keep it on Babylon — never port it, never start a new
game on it.)

## Allowed script tags (copy EXACTLY)

Put the tag(s) in `<head>` BEFORE your inline app code. (The platform separately
injects the Usion SDK — never add that one yourself.)

```html
<!-- 2D games -->
<script src="https://usions.com/vendor/phaser/4.2.1/phaser.min.js"></script>

<!-- 3D games: three.js is ES modules — ONE import map, then your module script -->
<script type="importmap">
{ "imports": {
  "three": "https://usions.com/vendor/three/0.185.1/build/three.module.min.js",
  "three/addons/": "https://usions.com/vendor/three/0.185.1/examples/jsm/",
  "crashcat": "https://usions.com/vendor/crashcat/0.0.3/crashcat.min.js"
} }
</script>
<script type="module" src="game.js"></script>

<!-- Sound effects for ANY game (2D or 3D): the tiny ZzFX synth, an ES module.
     In a module file:  import { zzfx } from 'https://usions.com/vendor/zzfx/1.4.0/ZzFX.js';
     or add "zzfx": "https://usions.com/vendor/zzfx/1.4.0/ZzFX.js" to the import map. -->
```

No other CDN, no other version, no other library (no three.js from
jsdelivr/unpkg/esm.sh — only the hosted copy above; no jQuery, no Google
Fonts). An import map may point ONLY at the platform's vendor folder, exactly
as written above; any other address is refused when the app is hosted. Assets too: never load
textures/models/sounds from other sites at runtime — use files shipped inside
the app (relative paths), the platform's hosted kit assets, or draw with the
engine.

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

## three.js (3D)

`game.js` is a module script (it runs after the page is parsed; the injected
`Usion` global is already there):

```javascript
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

Usion.init(async function (config) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));   // phones: never more than 2
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  document.getElementById('game').appendChild(renderer.domElement); // <div id="game"> filling the page

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x8fd3ff);
  scene.fog = new THREE.Fog(0x8fd3ff, 40, 160);
  const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 400);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x5a6b7a, 1.2));
  const sun = new THREE.DirectionalLight(0xffffff, 2.2);
  sun.position.set(12, 24, 10); sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024);
  scene.add(sun);

  const clock = new THREE.Clock();
  renderer.setAnimationLoop(function () {
    const dt = Math.min(clock.getDelta(), 0.05);                   // clamp: a hidden tab returns a huge dt
    update(dt);                                                    // your game step
    renderer.render(scene, camera);
  });
  window.addEventListener('resize', function () {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
});
```

- **Add-ons**: the add-ons of three 0.185.1 are hosted under
  `three/addons/` — `loaders/` (GLTFLoader, OBJLoader, FBXLoader, FontLoader…),
  `controls/`, `postprocessing/` (EffectComposer, RenderPass, UnrealBloomPass,
  OutputPass, ShaderPass…), `shaders/`, `utils/`, `objects/` (Sky, Water…),
  `environments/RoomEnvironment.js`, `geometries/`, `helpers/`, `lights/`,
  `lines/`, `math/`, `curves/`, `modifiers/`, `animation/`, `misc/`.
  NOT available: `DRACOLoader`, `KTX2Loader` and Basis textures (their
  decoders are not hosted — ship plain `.glb`), and the WebGPU / TSL / node
  add-ons (`three/webgpu`, `three/tsl`, `nodes/`). Use `WebGLRenderer`.
- **It must look like a place, not a demo**: a ground, a sky colour + fog,
  one hemisphere light + one shadow-casting sun, `MeshStandardMaterial`
  everywhere. Never unlit boxes floating in a void.
- **Models**: a `.glb` shipped INSIDE the app, loaded by relative path —
  `new GLTFLoader().load('assets/truck.glb', (gltf) => scene.add(gltf.scene))`.
  Keep each under ~700 KB. With no model, build the object from grouped
  rounded primitives (`CapsuleGeometry`, `SphereGeometry`, `CylinderGeometry`,
  bevelled boxes) — a readable silhouette, 3-6 parts, not one cube.
- **Repeat cheaply**: trees, cones, crowd, track pieces → `InstancedMesh` or
  clones sharing geometry/material. Budget for a mid phone: under ~150 draw
  calls, one shadow light, no more than ~300k triangles.
- **Camera makes the game**: a chase camera that eases behind the player
  (`camera.position.lerp(target, 1 - Math.exp(-6 * dt))`, then `lookAt`), never
  a fixed overhead view unless the game is a board.
- **Controls are touch-first**: an on-screen joystick / buttons as a DOM
  overlay (`touch-action: none`), plus keyboard for desktop.
- Dispose what you remove (`geometry.dispose()`, `material.dispose()`); pause
  the loop's game step while `document.hidden`.

### Physics for three.js: crashcat (rigid bodies)

Simple motion (a runner, a paddle, a ball with gravity) needs no physics
engine — integrate velocity yourself. For real rigid bodies (things that
collide, roll, stack, cars) use the hosted `crashcat`:

```javascript
import { registerAll, createWorldSettings, createWorld, addBroadphaseLayer, addObjectLayer,
         enableCollision, updateWorld, rigidBody, box, sphere, MotionType } from 'crashcat';

registerAll();                                           // once, before anything else
const settings = createWorldSettings();                  // gravity defaults to [0, -9.81, 0]
const BP_MOVING = addBroadphaseLayer(settings), BP_STATIC = addBroadphaseLayer(settings);
const MOVING = addObjectLayer(settings, BP_MOVING), STATIC = addObjectLayer(settings, BP_STATIC);
enableCollision(settings, MOVING, STATIC);
enableCollision(settings, MOVING, MOVING);
const world = createWorld(settings);

rigidBody.create(world, { shape: box.create({ halfExtents: [20, 0.5, 20] }),   // the floor
  motionType: MotionType.STATIC, objectLayer: STATIC, position: [0, -0.5, 0] });
const ball = rigidBody.create(world, { shape: sphere.create({ radius: 0.5 }),
  motionType: MotionType.DYNAMIC, objectLayer: MOVING, position: [0, 5, 0],
  restitution: 0.5, friction: 0.6 });

// every frame: step, then copy the body onto its mesh
updateWorld(world, undefined, dt);
mesh.position.fromArray(ball.position);
mesh.quaternion.fromArray(ball.quaternion);
// push it: rigidBody.setLinearVelocity(world, ball, [vx, vy, vz]);
// read it: ball.motionProperties.linearVelocity  ->  [vx, vy, vz]
```

Positions, velocities and quaternions are plain arrays, not THREE objects.

### Walk-around worlds (third-person character)

No physics engine needed — move the character yourself:

```javascript
const ray = new THREE.Raycaster();
const down = new THREE.Vector3(0, -1, 0);
const vel = new THREE.Vector3();
let onGround = false;

function stepPlayer(dt, input) {           // input.x / input.z in [-1, 1] from the joystick, input.jump
  const yaw = cameraYaw;                   // move relative to where the camera looks
  const fwd = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw));
  const right = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
  const want = fwd.multiplyScalar(-input.z).add(right.multiplyScalar(input.x)).multiplyScalar(6);   // 6 m/s
  vel.x += (want.x - vel.x) * Math.min(1, 12 * dt);
  vel.z += (want.z - vel.z) * Math.min(1, 12 * dt);
  vel.y -= 22 * dt;                                                 // gravity
  if (onGround && input.jump) vel.y = 9;
  player.position.addScaledVector(vel, dt);
  ray.set(player.position.clone().setY(player.position.y + 1), down);
  const hit = ray.intersectObjects(walkable, true)[0];              // walkable = [ground, platforms...]
  onGround = !!hit && hit.distance <= 1.02 && vel.y <= 0;
  if (onGround) { player.position.y = hit.point.y; vel.y = 0; }
  if (want.lengthSq() > 0.01) player.rotation.y = Math.atan2(vel.x, vel.z);
  if (player.position.y < -20) respawn();                           // fell off the world
}
```

Walls: keep the player inside by clamping to the level bounds or testing the
next position against wall boxes (`Box3.containsPoint`) before moving. Camera:
ease to a point behind and above the player, then `lookAt` the player.

## Multiplayer with an engine

The host-authoritative contract (see the multiplayer reference) does not
change: **only the host (`config.playerIds[0]`) runs the simulation/physics.**

- Host: steps physics, broadcasts compact snapshots 10–20×/s —
  `Usion.game.realtime('state', { players: { [id]: { x, y, z, ry } } })`.
- Guests: do NOT run physics for shared objects. Render meshes
  and smoothly lerp them toward the latest snapshot; send inputs with
  `Usion.game.realtime('input', { dir, jump })`.
- Two physics engines stepping independently WILL diverge — never mirror the
  sim on guests and hope it matches.

## Engine pitfalls (observed — do not repeat)

- Loading any script other than the pinned URLs above — stripped at deploy,
  app breaks. Copy the tags exactly.
- Creating the game/engine before `Usion.init` fires.
- `setInterval` game loops — use the engine's loop
  (Phaser `scene.update` / three.js `renderer.setAnimationLoop`); pause when
  the page is hidden.
- No resize handling (three.js: camera aspect + `renderer.setSize`) or a
  fixed-size Scale config (Phaser) — game doesn't fit the embedded frame.
- Hundreds of dynamic bodies — keep it under ~100; these run on low-end phones.
- Loading fonts/textures/models from external URLs — draw or embed instead.
- three.js: importing from a CDN or an add-on that is not in the hosted list
  (the import fails and the page stays blank); forgetting the import map;
  `<script src="game.js">` without `type="module"`; no lights (everything
  black); `setPixelRatio(window.devicePixelRatio)` uncapped (a 3x phone melts).
- Turning a 3D request into a flat top-down canvas game.
