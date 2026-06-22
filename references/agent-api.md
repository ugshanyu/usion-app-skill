# Registering & managing services from an AI agent (REST API)

A creator can let their **AI agent** create and manage Usion services
autonomously by handing it a **creator API key**. The agent drives the creator
REST API with `Authorization: Bearer <key>` — no human in the loop, no expiring
session. This is the agent-friendly alternative to the in-chat AI Creator bot.

Base URL `{API_URL}` = the Usion backend (e.g. `https://mobile.mongolai.mn`).

---

## 1. Get an API key (the creator does this once, by hand)

The creator mints a long-lived key and pastes it into their agent:

```
POST {API_URL}/auth/creator/api-keys
Authorization: Bearer <creator session JWT>      # from POST /auth/creator/token
Content-Type: application/json
{ "name": "my creator agent" }

→ 200 { "id": "...", "name": "my creator agent",
        "key": "usk_live_AbC…",                  ← the full key, shown ONCE
        "key_preview": "usk_live_AbC…", "created_at": "..." }
```

- The `key` is revealed **exactly once** — store it now; it is never retrievable.
- List keys (previews only): `GET {API_URL}/auth/creator/api-keys`
- Revoke a key (immediate, irreversible): `DELETE {API_URL}/auth/creator/api-keys/{id}`
- Lost a key? You can't read it back — revoke it and mint a new one.

## 2. The agent authenticates with the key

Every creator endpoint below accepts the key as a bearer token:

```
Authorization: Bearer usk_live_AbC…
```

It authenticates **as the creator** (full account access), never expires, and is
revocable. Treat it like a password.

## 3. Register a service — and capture its signing secret

```
POST {API_URL}/services
Authorization: Bearer usk_live_AbC…
{ "name": "My App", "iframe_url": "https://my-app.vercel.app",
  "description": "…", "tags": ["app"], "is_published": true }

→ 200  (the service) + "signing_secret": "…"   ← server-to-server secret, shown ONCE
```

- Required field: `name`. Common: `iframe_url`, `description`, `tags`,
  `is_published`, `image`.
- `signing_secret` is the per-service secret for server-to-server calls (e.g.
  the completion-notify endpoint). Store it in the service's **own backend env**
  (e.g. `USION_NOTIFY_SECRET`). It is **write-only** afterwards — no read returns
  it; if lost, rotate it (step 5).

## 4. Manage the creator's services

```
GET    {API_URL}/services            list the creator's services
GET    {API_URL}/services/{id}       one service
PUT    {API_URL}/services/{id}       update fields
DELETE {API_URL}/services/{id}       delete
```

## 5. Rotate a service's signing secret

```
POST {API_URL}/services/{id}/signing-secret/rotate
Authorization: Bearer usk_live_AbC…

→ 200 { "signing_secret": "…" }       ← new secret, shown once; old one dies immediately
```

## End-to-end (curl)

```bash
KEY="usk_live_AbC…"
API="https://mobile.mongolai.mn"

# register a service and grab its one-time signing secret
RESP=$(curl -s -X POST "$API/services" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"name":"My App","iframe_url":"https://my-app.vercel.app","is_published":true}')
SERVICE_ID=$(echo "$RESP" | jq -r .id)
SIGNING_SECRET=$(echo "$RESP" | jq -r .signing_secret)   # store this now
```

## Security notes

- The API key grants **full creator access** — paste it only into an agent you
  trust, and revoke + re-mint if it leaks.
- Keys are stored **hashed** server-side and shown once (the API-key model).
- The per-service `signing_secret` (steps 3 & 5) is a *separate* secret used to
  HMAC-sign server-to-server requests — see `references/publishing.md`.
