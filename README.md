# usion-app — Claude Code skill for building Usion mini-apps

A [Claude Code skill](https://docs.claude.com/en/docs/claude-code) that teaches
Claude how to build, test, and publish mini-apps and games for the
[Usion](https://usions.com) platform using the Usion SDK
([`@usions/sdk`](https://www.npmjs.com/package/@usions/sdk)).

## What's inside

| File | Purpose |
|------|---------|
| [SKILL.md](SKILL.md) | Entry point: delivery paths, app skeleton, platform rules, capability map, publish summary |
| [references/sdk-reference.md](references/sdk-reference.md) | Complete `Usion.*` API surface — user, wallet, storage, cloud KV (with quotas), game, lobby, matchmaking, leaderboard, netcode, chat, bot, sharing |
| [references/multiplayer.md](references/multiplayer.md) | Host-authoritative multiplayer pattern, turn-based vs realtime channels, netcode recipes (interpolation, prediction, delta snapshots, lockstep, WebRTC mesh, WebTransport) |
| [references/publishing.md](references/publishing.md) | Hosting paths, service registration, quality-checker rules, and the live exemplar catalog |

## Install

Copy this directory into your project's skills folder:

```bash
git clone https://github.com/ugshanyu/usion-app-skill .claude/skills/usion-app
rm -rf .claude/skills/usion-app/.git
```

Or into your personal skills at `~/.claude/skills/usion-app`. Claude Code picks
it up automatically; it triggers whenever you ask for a Usion mini-app, game,
or anything touching the Usion SDK.

## Reference mini-app repositories

Real, deployed apps to study — each demonstrates a different SDK pattern:

| Repo | Live | Demonstrates |
|------|------|--------------|
| [usion-example-turnbased](https://github.com/ugshanyu/usion-example-turnbased) | [usion-example-turnbased.vercel.app](https://usion-example-turnbased.vercel.app) | Official turn-based reference (Space Invaders Duel) — `Usion.game.action()`/`onAction` |
| [usion-example-realtime](https://github.com/ugshanyu/usion-example-realtime) | [usion-example-realtime.vercel.app](https://usion-example-realtime.vercel.app) | Official real-time reference (Tag Arena) — host-authoritative loop + direct game server |
| [usion-pong-webrtc](https://github.com/ugshanyu/usion-pong-webrtc) | [pong-webrtc-production.up.railway.app](https://pong-webrtc-production.up.railway.app) | WebRTC DataChannel with WebSocket fallback, network simulation |
| [usion-contra-p2p](https://github.com/ugshanyu/usion-contra-p2p) | [contra-p2p-production.up.railway.app](https://contra-p2p-production.up.railway.app) | Browser-to-browser P2P WebRTC co-op, platform signaling only |
| [space-craft-v2](https://github.com/ugshanyu/space-craft-v2) | [space-craft-v2-production.up.railway.app](https://space-craft-v2-production.up.railway.app) | 4-player server-authoritative shooter, dual transport, lag compensation |
| [space-craft-standalone](https://github.com/ugshanyu/space-craft-standalone) | — | Standalone-mode game (own socket, no host iframe) |
| [usion-xo-platform](https://github.com/ugshanyu/usion-xo-platform) | [usion-xo-platform.vercel.app](https://usion-xo-platform.vercel.app) | XO 8×8 (5-in-a-row) platform-mode game |
| [mongolgpt-studio](https://github.com/ugshanyu/mongolgpt-studio) (private) | [kling-studio.vercel.app](https://kling-studio.vercel.app) | Content-creation app: AI video/image generation, wallet billing, share-to-feed |

The SDK itself: bundle at https://usions.com/usion-sdk.js, design tokens at
https://usions.com/usion-design-system.css, npm package
[`@usions/sdk`](https://www.npmjs.com/package/@usions/sdk).

## Keeping it in sync

The canonical copy of this skill lives in the Usion monorepo at
`.claude/skills/usion-app/`; this repo is the public, installable mirror. When
the SDK gains new modules, update both.
