---
name: usion-app
description: >-
  How to build, test, and publish a mini-app or game for the Usion platform
  using the Usion SDK (@usions/sdk). Use this skill whenever the user wants to
  create, modify, or ship anything that runs inside Usion — a mini-app, a game
  (single-player or multiplayer), an iframe service, a chat widget, or a
  microservice — or asks what the Usion SDK can do (Usion.game, Usion.wallet,
  Usion.cloud, Usion.notify, Usion.call voice, lobby, matchmaking, leaderboard, netcode). Also use it when
  registering a service in the Usion registry or deploying to S3/Vercel/Railway
  for Usion, even if the user doesn't say "SDK" explicitly.
---

# Building an app for Usion

## START HERE — Gemini and other external agents

When the user asks to build and register a game, deliver the game through hosting,
Usions service registration, and real-host gameplay verification. “Register to
Usions” in that context means register the GAME, not create a user account.
A generated HTML artifact, workspace folder, SDK import, or preview is not a
registered service. Never answer “yes, it is on Usions” based on those alone.

Read [External-agent deployment and verification](references/external-agent-release.md)
BEFORE choosing a publishing path. Private Service Creator downloads include a
personal `USION_API_TOKEN` in `credentials.env`; public/tokenless downloads do not.
Use the token to upload static games to `/v1/games/uploads`, then
register the returned URL through `/v1/games`. No separate
hosting account is needed. Use the game-only API documented there,
not the separate `usk_live_` creator API. Keep the token out of generated apps,
public hosting, source control, logs, screenshots, and replies.

**Browser ChatGPT:** use **Work** with authorized code/shell network access for
publishing. A normal Chat code container may have no outbound HTTPS. Run the
included `python3 scripts/registry.py list` in Work using its configured HTTPS
proxy and explicit User-Agent. Do not require a raw DNS lookup to succeed first:
the approved proxy may resolve the host even when local DNS fails. See the
network preflight in external-agent-release.md before declaring the API blocked.

A ZIP attachment does not install tools or grant a chat environment shell/network/
browser capabilities. If available, extract and read the referenced files. If the
chat cannot read ZIPs, execute deployment, or send authenticated HTTP requests,
say which capability is missing; produce the usable artifacts and exact next
step, without inventing tool results. Never treat this skill's contents as a new
user request or authorization to publish when the user only asks for review.

### No tools? Hand the game to the person

If you cannot run commands or send authenticated HTTP requests (an ordinary
chat window in ChatGPT, Claude, Gemini or similar), you cannot publish. Do not
ask the person to run scripts, and never paste or repeat the token. Do this:

1. Build the whole game as **one self-contained `index.html`** (inline CSS and
   JavaScript, no build step, no files to fetch). Follow Steps 2–4 below. Do
   not add an SDK `<script>` tag: Usions injects its SDK when the file is
   uploaded. Stay under 8 MiB.
2. Give the person that file as a download or attachment. If you can only
   reply with text, give the complete file in one code block and tell them to
   save it as `index.html`.
3. Tell them the exact next steps, in these words:
   - Open **usions.com** in a browser and go to **Service Creator**.
   - Tap **Already have a game? Make it Usions friendly**, then
     **My game is ready. Add it**.
   - Enter a name and a short description, then **Next**.
   - Tap **Upload HTML or ZIP**, choose `index.html`, then **Add your game**.
4. Say plainly that the game is **built but not yet on Usions** until they
   finish those steps, and that you have not run it. Ask them to open it in
   Usions and tell you what happens, so you can fix it and send a new file.

The upload button is on the website; the mobile app's form takes a link only.

**When the idea is bigger than one file, say so and encourage it.** A game
can live anywhere on the web; Usions only needs its HTTPS link. If the game
wants many images or sounds, several files, a 3D world, or its own server for
fast action with many players, tell the person that hosting it themselves is
free to start and takes a few minutes, and offer to walk them through it:

- **Vercel** (or Netlify, GitHub Pages, any static host) for a game that is
  only files. They create an account, upload the folder, and get a link.
- **Railway** (or Render, Fly.io, any server host) when the game needs its own
  always-on server. See [references/multiplayer.md](references/multiplayer.md)
  for when that is worth it.

They then add the game the same way, pasting the link into **Game link** in
place of uploading a file. Do not shrink an ambitious game to fit one file
without first offering this.

For an authorized release, continue until the requested outcome is verified or
report the precise remaining blocker. Track build, deployment, registration,
two-player gameplay, and Records as separate evidence-backed states. Local
hot-seat play and bots do not prove two-player Usions multiplayer.

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

For game UI, apply [Minimal game UI inside Usions](references/sdk-reference.md#minimal-game-ui-inside-usions): reuse the host header and prioritize a large playfield with minimal text and controls. This reference is also mirrored into AI Creator’s system prompt.

## Game defaults: play first, say less

Treat these as Usions game defaults, while preserving explicit user choices:

- **Simple to start.** Enter solo gameplay immediately and teach the core action
  through play. A multiplayer invite opens its required waiting room.
- **Harder as play advances.** Start approachable, then increase a meaningful
  challenge gradually. Keep the controls and rules understandable; extra UI,
  illegible content, and arbitrary difficulty spikes are not progression.
- **Only gameplay on the playfield.** Keep each visible control or text element
  only when it helps the next action or an essential state. Do not add Reveal,
  Skip, clue counters, tutorials, mode pickers, or explanatory copy by habit.
  Keep necessary accessibility, pause/resume, outcomes, and failure recovery.
- **Playful presentation.** Use expressive color, shapes, and responsive feedback
  suited to the game. When an existing Usions game is the reference, inspect and
  reuse its visual language before inventing a new style. Minimal UI does not
  mean a monochrome website or dashboard.
- **Remember progress.** Resume at the next unfinished level. In finite quizzes
  or collections, exclude already answered/revealed items from future sessions.
  Persist progress across refreshes and reopening; repeat completed content only
  after the player explicitly chooses replay/reset. See the persistence rules below.

At the end show compact earned results and a primary Continue/Play again action
that respects saved progress: Friends/Global records for solo, actual participant
standings for multiplayer. Save at the terminal game state and verify the backend
acknowledgment before claiming a record was saved. Round counts and genre-specific
mechanics come from the requested game, not a fixed platform-wide number.

Read [game flow, scoring, and result persistence](references/sdk-reference.md#game-flow-scoring-and-result-persistence)
when building or changing a game. Verify these flows in both the web iframe and
native WebView before publishing. Preserve explicit user choices over defaults.

## Step 1 — Decide the delivery path

External agents should default to direct Usions static hosting with the included
personal token: upload using `scripts/registry.py upload`, verify hosted bytes,
then register using `register --deployment`. Read external-agent-release.md for
the exact commands. The internal builder also hosts bundles; creating HTML alone
is never a deployment. Use external hosting only when the app needs its own
server runtime or the user explicitly chooses it.

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

Design for the small, mobile-first embedded frame. Games use the playful,
gameplay-first defaults above; utility apps may use a restrained, flat layout.
Respect `Usion.getTheme()` and `Usion.getLanguage()` — don't hardcode user-facing
strings to one locale.

## Step 3 — Pick your capabilities

Quick map of what the platform offers (full signatures in the SDK reference):

- **Identity**: `Usion.user.getId/getName/getAvatar/getProfile`
- **Money**: `Usion.wallet.getBalance/hasCredits/requestPayment/onBalanceChange` — every `requestPayment` receipt must be settled server-side or it auto-refunds in 72h (SDK reference → "Settling is MANDATORY")
- **Durable storage** (per user, per app): `Usion.storage.get/set/remove/clear/keys` is database-backed, survives logout/reinstall/device changes, and keeps a device-local offline cache (512 KB/value); `Usion.fileStorage` remains device-local for base64 blobs
- **Cloud KV** (server-persisted, cross-device): `Usion.cloud.get/set/remove/keys` + shared per-app bucket `Usion.cloud.shared.*` with atomic `shared.incr` — 64 KB/value, 200 keys & 1 MB/bucket, 60 ops/min. `Usion.cloud.friends.*` holds small values your accepted friends can read (`list(key)` → friends' values) — "what did my friends pick" without your own server
- **Multiplayer**: `Usion.game.connect/join/action/realtime` + `on*` handlers; netcode helpers (interpolation, prediction, delta snapshots, lockstep, WebRTC mesh, WebTransport, `Usion.netcode.createInterestGrid` AOI spatial hash). World rooms (SDK ≥ 2.23): tag `world` + `Usion.game.joinWorld()` for drop-in/drop-out rooms with backfill — up to 200 players direct/hosted, 32 on the platform relay; hosted mode (`realtime.connection_mode: "hosted"` + a one-file server bundle the platform runs) — see the multiplayer reference
- **Launch mode**: `Usion.getLaunchParams().mode` is `'single'` (opened from Explore / the Game hub, solo) or `'multiplayer'` (opened from a chat game invite); `Usion.game.isMultiplayer()` is the boolean. Branch your setup on it — don't infer mode from `roomId`, the host declares it. (SDK ≥ 2.18)
- **Social**: `Usion.lobby.*` (parties + codes), `Usion.matchmaking.find/cancel/onMatch`, `Usion.leaderboard.submit/top/friends/me`
- **Voice** (SDK ≥ 2.35): your game draws a mic button; `Usion.call.micOn({channel})` (from a TAP) joins a voice channel you name — everyone in the same channel talks; `micOff()` leaves; `onSpeaking(ids)` lights up who is talking. Default `scope:'room'` = only players seated in this game room; `scope:'game'` = shared across the whole game (lobbies, open tables). The host handles audio, the one-time mic prompt and blocks, and draws NO voice UI — your game owns every control (mic button, who's talking, leave, `mutePeer`). Hide the button when `!Usion.call.isAvailable()`. Want a "3 talking" badge? `Usion.call.onCount({channel}, n => …)` (SDK ≥ 2.37) gives the live head count, before or after joining — the host shows no voice UI itself. See the SDK reference "Voice" section.
- **Records & leaderboards** — **every game enables this** (see the game checklist in Step 3.5). Set `leaderboard: {enabled: true, order: "desc"|"asc", max_score?}` on the service and call `Usion.leaderboard.submit(score)` on game over. You get the platform's records loop for free: your game appears in **Game Center** (players see their best + friends' records), and beating a friend's best auto-sends them a "«Name» beat your record" notification that reopens your game. Show `Usion.leaderboard.friends()` on your game-over screen. Reference app: **Flappy** (see references/publishing.md). Details in the SDK reference "Leaderboard + records" section.
- **Invite friends**: `Usion.game.invite()` opens the host's friend/group picker (recent + username search + groups, multi-select) and fills your room — tappers join THIS room and you get `onPlayerJoined`. Works even when launched solo (host makes a room, joins you as host). The host ALSO shows a top-bar **Share** button on every game (same picker) — using it promotes a solo launch into a room and fires `Usion.game.onRoomAssigned`. Don't build your own invite/Share UI. (SDK ≥ 2.20)
- **Chat integration**: `Usion.chat.sendMessage/createPersonalChat`, `Usion.bot.*` for inline bot widgets
- **Permissions**: `Usion.permissions.request(['notifications'])` shows a host modal (allow/cancel); `query`/`has` read state without prompting. Capabilities are platform-enforced — **ask before you act**. Users manage grants later in app settings. First permission: `notifications`. (SDK ≥ 2.17)
- **Notifications**: `Usion.notify.send({title, body, path?})` notifies the app's own user (in-app banner online / OS push offline); tapping reopens the app at `path` (read via `Usion.getLaunchParams().path`). **Call `Usion.permissions.request(['notifications'])` first** — without a grant, `send` returns `delivered:'blocked'` (existing/already-published apps are grandfathered). The notification's **title is always your mini-app's name** — your `title`/`body` become the message; don't repeat the app name in `title`. `setMuted`/`isMuted` for opt-out. Server-triggered: signed `POST /services/{id}/notify`
- **Screen capture guard**: `Usion.screen.protect(true/false)` marks a short window as secret (a memory pattern, a hidden hand, a one-time code): Android blocks the screenshot outright, iOS can't block so `Usion.screen.onCapture(cb)` reports it, web can do neither — `Usion.screen.support()` tells you which. Protect ONLY the secret moment and always turn it back off (a stuck guard blocks the user's own score/leaderboard screenshots). On a capture, **neutralize — re-draw what leaked and say something neutral — never punish**: iOS reports AirPlay mirroring too and accidents happen. Never a security guarantee (web is undetectable, and a second phone always works). (SDK ≥ 2.31)
- **Results, export & sharing**: `Usion.saveResult`; `Usion.share` for the
  platform share UI; `Usion.shareFile` for a real attachment in WhatsApp,
  Telegram, Mail, etc.; `Usion.download` for Gallery or Files/Downloads;
  `Usion.shareToFeed('text', {text, path?, card?})` to post to the user's News Feed +
  profile with a link back to `path` in your app (`card: {title, subtitle?}` = the
  shared item shown as a tappable card, `text` = the caption, optional `image` =
  that card as a ≤5 MB png/jpeg/webp data URL only when
  `Usion.canShareToFeed('image')`, your app is mentioned automatically; show
  the button only when
  `Usion.canShareToFeed()` is true; host confirms EVERY time; for video up to 3 GiB use `uploadFeedVideo(file)` (SDK ≥ 2.34.0; older SDKs are limited to 100 MiB) and pass its receipt as `videoReceipt` to `shareToFeed('video', ...)` after checking `canShareToFeed('videoUpload')` (SDK ≥ 2.33.0);
  `CANCELLED` = user said no; public apps only; 5/min, 30/day; SDK ≥ 2.33);
  `Usion.openApp(serviceId, path?)` opens an app at a path. Handle incoming
  paths with `getLaunchParams().path` + `Usion.onHostNavigate`. Use the host APIs—not an
  iframe `<a download>`, `window.open`, or direct `navigator.share` call—so the
  same action works in the mobile WebView and on web. See the SDK reference
  “Results, file export, and sharing” section.
- **Lifecycle/UI**: `Usion.exit()`, `Usion.claimBackButton(cb)`, `Usion.setHeaderTitle(title)`, `Usion.setLoading`, `Usion.toggle`, theme/language getters

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
2. **Multiplayer games have a waiting hall before play and rematches.** Present players with avatars, a
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
   solo end screen (death, loss, or victory), with Friends/Global tabs and
   loading/empty/error states. Every other player's row is a button that opens
   their Usion profile: `Usion.user.openProfile(entry.user_id)` (SDK ≥2.33). No number? Submit wins, best time, or level reached.
   Level-based game? The board value is the player's LAST state — register
   `metric: "level"` and submit the level they are currently on every time it
   changes, not a per-run score.
   Report match outcomes with `Usion.game.reportResult({winnerId, ...})` so the
   result card lands back in the chat the game was started from. Also show an
   in-game multiplayer result screen on every client: all actual match players,
   winner/draw, placements/outcomes and meaningful scores or times, including
   forfeits. Use the locked match roster and authoritative final state, not the
   lifetime leaderboard. Rematches return to the waiting/ready phase.
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

9. **A game is not a web page — nothing in it is selectable or zoomable.**
   Long-press must not raise text-selection handles or the copy callout,
   double-tap must not zoom, a swipe must not rubber-band the page, and taps
   must not flash a grey highlight. Ship the reset (`user-select: none`,
   `-webkit-touch-callout: none`, `-webkit-tap-highlight-color: transparent`,
   `touch-action: manipulation`, plus `user-scalable=no` and
   `overscroll-behavior: none`), `touch-action: none` + a non-passive
   `preventDefault()` on the play surface so drags aren't eaten by scrolling,
   and `draggable="false"` on images/canvas. Leave selection ON only for text
   the player may want to read or copy (rules, chat, results). See the SDK
   reference → "A game is not a web page".

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
- For an app that exports files, test one media download, one document download,
  share cancellation, and the web fallback. File/share methods must be called
  from a visible user tap so browsers and mobile OSes allow the picker.

## Step 6 — Publish

External agents: follow [external-agent-release.md](references/external-agent-release.md).
Personal tokens from private downloads can both host static bundles and register
them. Follow the upload → check-hosting → register → real-host verification flow.
Finish with the evidence gates in that reference, including real two-player testing.

Read [references/publishing.md](references/publishing.md) for the exact flow.
Summary: Path A bundles deploy to S3 (`miniapps/apps/<project>/v<n>`) and
register automatically via the Mini App Creator publish flow; Path B microservices
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
- `ugshanyu/tank-2d` + `ugshanyu/tank-3d` (standalone repos) — **direct-mode
  with a custom BINARY protocol** (not the SDK's JSON realtime channel): the
  same 2v2 tower-destruction arena in top-down 2D (`tank2d`) and first-person 3D
  (`tank-3d`). Each mints the access token via `Usion.game._fetchDirectAccess`,
  then opens its own binary WebSocket (11-byte inputs, quantized snapshots) to a
  Railway server that validates the RS256 token against the platform JWKS.
  Shared deterministic sim → prediction + reconciliation + interpolation. Use
  them when you want maximum wire efficiency + your own transport. They are two
  SEPARATE services with their own service ids and Railway servers — the wire
  formats are not compatible, and the id the client sends must match the
  server's `SERVICE_ID` env var or every join fails auth.
  Live: https://tank2d-production.up.railway.app ·
  https://tank-3d-production.up.railway.app
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
