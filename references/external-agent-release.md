# External-agent release: deploy, register, prove

Use this workflow when Gemini or another external agent is asked to build and
publish a Usions game. It supplements the existing SDK and multiplayer references.

## 1. Establish actual capabilities

You need file/code execution and outbound HTTPS. Usions hosts static games using
the included token: no AWS, Vercel, Railway or separate hosting account is needed.
Registration accepts only game metadata and an iframe_url from your own Usions
upload receipt. Existing owned games may be updated; new code must be uploaded
first. Custom-server configuration, bot fields, and unknown fields are rejected.
Platform multiplayer is supported.

Real multiplayer verification also requires browser/device access to two distinct
authorized Usions accounts; genuinely solo games require real-host solo testing. Inspect
available tools instead of assuming Gemini Canvas or an HTML preview can deploy.
Use available capabilities to finish independent work. If a dependency is absent,
report it exactly; do not give generic account-signup advice or fabricate success.
User authorization to build and register covers the intended game's release,
not other services, token rotation, account creation, or unrelated infrastructure.

## 2. Use the included credential correctly

`credentials.env` beside SKILL.md in a private download contains
`USION_API_TOKEN=usion_sk_…`. It expires within 30 days and can be revoked in
Service Creator. Public/tokenless downloads omit it. If absent, use an already
authorized personal token or ask for a private download/token; do not invent one.
Read it programmatically without printing it or sourcing arbitrary shell content.
Base API: `https://agents.usions.com`. Send it only to this API as
`Authorization: Bearer <token>`; never put it in HTML, browser JavaScript,
query strings, public repositories, or hosting folders. Do not forward the header
across redirects. The SDK uses host-provided player identity; it does NOT use this token.

Read-only preflight:

```
GET /v1/games
```

200 plus a valid list confirms registry access. Use an explicit application
User-Agent, e.g. `UsionsRegistryHelper/1.0`; the included helper sets it. Some edge
filters reject Python's default `Python-urllib` user agent with HTTP 403 even
while curl and identified application clients work.

An HTTP response means the server/edge was reached. Distinguish DNS failure,
connection/TLS failure, timeout, HTTP 401, and HTTP 403. Never call the server
“unreachable” merely because a request returned 403. Use authenticated `GET /v1/games` as the preflight. The gateway deliberately
returns 404 for `/health`, `/docs`, and every unrelated route. Compare curl
or the helper's explicit User-Agent. Do not disable TLS verification, expose credentials, or bypass a
login/challenge. If access is still denied, report the URL, client, HTTP status
and sanitized diagnostic; do not claim a global outage. A registry 401 indicates
missing/invalid/expired authentication; request a replacement only when needed.
Do not silently try other auth families. This token grants only `games:upload`, `games:read`, `games:create`, and
`games:update`. It cannot delete games, mint credentials, rotate notification
secrets, create bots/apps/skills, or access chat/wallet/admin APIs. Calling the old
backend URL does not bypass these restrictions. It is not a player login and does not authenticate two test players.

Use `python3 scripts/registry.py list` from this skill directory. It reads the
credential privately and prints only selected service metadata. No live request
has been pre-executed by packaging this skill.

## 3. Build genuine multiplayer

Read `multiplayer.md` and the SDK reference. For a two-player duel implement real
Usions connect/join, player handlers, waiting/ready flow, synchronized turns or
host-authoritative state, disconnect recovery, results, and rematches. Register
handlers before solo launch so `onRoomAssigned` can promote it to multiplayer.
Keep any solo bot mode separate. Two tanks controlled on one keyboard are local
hot-seat mode, not online multiplayer. Tags alone do not implement networking.

## 4. Upload and host directly on Usions — default for static games

Keep a game-only deployment directory separate from this private skill. Do NOT
upload the skill ZIP or credentials.env. A single index.html works; multi-file
games may include local JS/CSS, images, audio/video, fonts, WASM and GLB assets.
For network multiplayer use the platform SDK relay/rooms; this upload does not
execute Node/Python/PHP server code. Custom servers still need a server runtime.

Run from this skill directory (the helper reads credentials.env privately):

```sh
python3 scripts/registry.py list
python3 scripts/registry.py upload /absolute/path/to/game-folder --output /absolute/path/to/deployment.json
python3 scripts/registry.py check-hosting /absolute/path/to/deployment.json
```

`upload` also accepts `/path/game.zip` or `/path/index.html`. It creates a
reproducible ZIP for a directory. Hosting is performed by **Usions**, not by the
agent's local preview or an external hosting provider. Do not tell the user to
manually upload through the internal Mini App Creator after these steps.

Wire API (for agents with HTTP tools but no Python):

```
POST https://agents.usions.com/v1/games/uploads
Authorization: Bearer <USION_API_TOKEN>
User-Agent: UsionsRegistryHelper/1.0
Content-Type: application/zip

<raw ZIP bytes, NOT JSON, base64 or multipart>
```

For one HTML file use `Content-Type: text/html` with its raw UTF-8 bytes. Response:

```json
{
  "deployment_id": "<returned ID>",
  "status": "hosted",
  "iframe_url": "https://<Usions-storage>/miniapps/agent/.../index.html",
  "base_url": "https://<Usions-storage>/miniapps/agent/.../",
  "files": [{"path":"index.html","url":"https://.../index.html","bytes":1234,"sha256":"..."}],
  "sdk_injected": true,
  "registration_required": true
}
```

Use the **returned** URLs; never construct the storage domain or guess a URL.
Usions injects its SDK into HTML. Do not add a different SDK major/CDN runtime;
bundle dependencies locally or use the allowed `https://usions.com/vendor/`
runtimes. The receipt hashes describe the **served bytes after SDK injection**,
so local HTML may differ. `check-hosting` fetches every returned asset without
credentials and verifies the hash and length. Also load the hosted game in a
browser and inspect runtime errors: matching files alone does not prove gameplay.

Limits: 12 MiB uploaded, 24 MiB expanded, 8 MiB/file, 128 files, 20 uploads/hour
and 50/day per creator. Put index.html at the ZIP root. Use relative file paths
with letters/numbers/dots/underscores/hyphens/slashes; no hidden files, traversal,
symlinks, credentials, encrypted ZIPs or unsupported source/tooling files.
The hosted files are publicly readable even for a private registry service;
never upload secrets. Registration does not change the static files' visibility.

Identical prepared content for the same owner returns the same immutable
deployment and receipt, making upload retries safe. Read a receipt with
`python3 scripts/registry.py deployment DEPLOYMENT_ID` or authenticated
`GET /v1/games/uploads/{deployment_id}`. Another owner cannot read it.
Changed content gets a new URL; update the intended service instead of creating
another listing. Storage failures return 503 and never claim success. HTTP 413
means reduce file size, 422 means fix the bundle, 429 means wait for the quota.
Do not work around quota by minting more credentials. Only the following routes exist on the gateway: `POST /v1/games/uploads`,
`GET /v1/games/uploads/{deployment_id}`, `GET /v1/games`, `POST /v1/games`,
`GET /v1/games/{id}`, and `PUT /v1/games/{id}`. All require the corresponding
token scope. Status and listing are owner-only. Publish/unpublish an owned game
using PUT with `is_published`; deletion is intentionally unavailable.
Registration is separate and must succeed before saying the game is on Usions.

## 5. Register only the intended game

Check `/v1/games` first. Reuse an existing service only when its
identity and URL establish that it is the same intended game; ambiguous matches
need clarification. Do not blindly create duplicates on retries.

Write `registration.json` outside the public game directory. For direct hosting,
omit iframe_url/image: the commands below fill them from the verified receipt.

```json
{
  "name": "Pocket Tanks Arcade",
  "description": "Two-player turn-based tank battles",
  "service_type": "game",
  "cost": 0,
  "tags": ["game", "multiplayer", "iframe"],
  "genre": "strategy",
  "max_players": 2,
  "is_published": true,
  "realtime": {
    "connection_mode": "platform",
    "connection_transport": "websocket"
  },
  "leaderboard": {"enabled": true, "order": "desc"}
}
```

Adapt name, genre, ranking order/metric, capacity and transport to the implemented
game. Register with the verified hosting receipt:

```sh
python3 scripts/registry.py register /path/registration.json --deployment /path/deployment.json --icon icon.png
```

Omit `--icon` if no icon was uploaded. For an existing game use
`update SERVICE_ID /path/registration.json --deployment /path/deployment.json --icon icon.png`.
The helper selects the icon URL from the actual manifest. Without the helper,
set iframe_url to the returned entry URL and image to the returned icon URL. Read current server validation errors;
do not invent fields or switch SDK major versions to bypass a rejection.

```
POST /v1/games       # new service, normally HTTP 201
PUT /v1/games/{id}         # intended existing service only
GET /v1/games/{id}            # authenticated owned-game status
```

The bundled helper supports `upload`, `deployment`, `check-hosting`, `list`,
`register`, `update`, and `verify SERVICE_ID`. It makes one
request per invocation and does not automatically retry writes. Save returned
service ID immediately. After a timeout/uncertain write response, list services
and reconcile the outcome before retrying. Fix explicit 422 payload errors;
stop on auth failure or unresolved ownership rather than using database access.

Registration proof requires: successful write, owner readback (`verify ID`),
and public readback (without the token, via
`https://usions.com/api/proxy/registry/services/ID`) of the SAME ID with intended iframe_url, published state, game and
multiplayer tags, capacity (returned under game_config), realtime configuration,
and leaderboard settings. Then open it from the actual Usions host. A 201 alone
does not prove listing visibility or gameplay. Preserve the returned ID; do not
invent a Usions launch-link format—copy the actual host's share link when available.

## 6. Real-host acceptance gate

For a genuinely solo game (such as classic Snake), play a full run in the real
Usions host and verify Records as below; do not invent a second-player requirement.
For a multiplayer game, every two-player check below is required.

Use TWO distinct signed-in Usions accounts in separate sessions/devices, on the
registered deployed service. Use existing authorized test accounts; if unavailable,
report `registered; real two-player verification blocked` and the missing access.
Two tabs with one identity, a mock SDK, synthetic INIT, bots, bare hosted-page
sessions, or local hot-seat play do not pass this gate.

Record the tested service ID, build/revision, time, clients, room ID, and redacted
player identities. Keep screenshots or a short recording plus relevant sanitized
network/console evidence. Observe, rather than assume:

1. Player A opens the registered game in Usions and invites B through the host.
2. B opens the invite; both see the same room and two distinct players in the
   waiting hall. Ready/start reaches the same match on both clients.
3. Each player performs meaningful legal gameplay. For tanks, A and B each fire;
   both clients agree on turn order, projectile outcome, terrain, damage and health.
   Verify out-of-turn input cannot advance the match or double-apply a move.
4. Complete a legitimate match. Both clients agree on winner/draw and results;
   the platform result flow is acknowledged. A rematch returns through ready/start.
5. Briefly disconnect/reload one client; verify the documented recovery or fair
   forfeit outcome without duplicated moves or a permanently stuck match.
6. For Records, earn and submit a real score through the deployed host; inspect
   the acknowledgment and reload the platform Records page to verify that new
   score under the registered metric. Existing rows and local saved labels do
   not count. See records-verification.md.

Use SDK network simulation as additional testing, not a replacement for two
actual host sessions. If the final build changes, repeat affected live checks.
API readback is API evidence, not visual UI verification.

## 7. Completion language must match evidence

Report these separately, with evidence or a concrete blocker:

- Build: artifact/source location and tested revision.
- Deployment: verified production URL and served build identity.
- Registration: returned service ID and verified public metadata.
- Two-player: real-host test outcome, session evidence and observed match result.
- Records: earned submission acknowledgment and reloaded platform result.

Only say the requested release is complete or “registered and verified playable
with two players” after all applicable gates pass. Valid partial reports include:
“Built; upload blocked: this environment cannot send HTTP requests”, “Deployed;
registration failed: HTTP 401”, and “Registered; real two-player verification
blocked: second signed-in test account unavailable”. Do not blame caching or
claim another system completed work without checking it. A user request to
register a game is never answered with instructions for downloading Usions and
creating a personal account.
