# Frontend deployment (Vercel)

T-Clipper’s Next.js app lives in this folder. Backend stays on Railway.

## Prerequisites

- Railway API already deployed and reachable over **HTTPS**
- Vercel account connected to this GitHub repo
- Railway `CORS_ORIGINS` can be updated after you know the Vercel URL

## Root Directory (required)

This is a monorepo. In the Vercel project settings:

| Setting | Value |
|---------|--------|
| **Root Directory** | `frontend` |
| Framework Preset | Next.js (auto) |
| Build Command | `npm run build` (default from `package.json`) |
| Output | Next.js default (do not set a static export) |
| Install Command | `npm install` (default) |

Do **not** set the Root Directory to the repo root — the Next.js app is only under `frontend/`.

## Environment variables (Vercel)

Set under **Project → Settings → Environment Variables** for **Production**:

| Name | Required | Example |
|------|----------|---------|
| `NEXT_PUBLIC_API_BASE` | **Yes** | `https://your-api.up.railway.app` |
| `NEXT_PUBLIC_POLL_INTERVAL_MS` | No | `5000` |

Rules for `NEXT_PUBLIC_API_BASE`:

- No trailing slash
- Must be `https://` in production
- Must not be `localhost` / `127.0.0.1`
- Must match the Railway public API URL browsers will call

`NEXT_PUBLIC_*` values are inlined at **build time**. After changing them, **redeploy**.

Local development uses `frontend/.env.local` (see `.env.example`). Localhost fallback is allowed only when `NODE_ENV !== "production"`.

## Exact Vercel steps

1. Open [vercel.com](https://vercel.com) → **Add New** → **Project**.
2. Import the `ai-video-repurposer` Git repository.
3. Before deploying, set **Root Directory** to `frontend` (Edit → `frontend`).
4. Add Production env:
   - `NEXT_PUBLIC_API_BASE` = `https://<your-railway-api-host>`
5. Click **Deploy**.
6. Copy the production URL (e.g. `https://t-clipper.vercel.app`).
7. Update Railway CORS (next section), then hard-refresh and smoke-test.

### Preview deployments (optional)

If you use Vercel Preview URLs, either:

- Add those origins to Railway `CORS_ORIGINS`, or
- Disable Preview Deploys until CORS is ready

Production-only Closed Beta: ship Production and skip Preview CORS for now.

## Railway configuration (backend pairing)

No backend code changes. Update **service variables** only.

### Required for the frontend to work

| Variable | Action |
|----------|--------|
| `CORS_ORIGINS` | Include the Vercel production origin |

Example (keep local for DIY debugging):

```text
CORS_ORIGINS=https://t-clipper.vercel.app,http://localhost:3000,http://127.0.0.1:3000
```

If you use a custom domain or `www`, add those exact origins too (scheme + host, no path).

After changing `CORS_ORIGINS`, **restart / redeploy** the Railway service so settings reload.

### Verify Railway API

```text
GET https://<your-railway-api-host>/health
→ {"status":"ok"}
```

Confirm clip media is served from the same host:

```text
https://<your-railway-api-host>/media/clips/<filename>
https://<your-railway-api-host>/media/download/<filename>
```

### HTTPS

The Vercel site is HTTPS. The API base **must** be HTTPS. Mixed content (HTTPS page → HTTP API) will fail in the browser.

## Local production build check

From `frontend/`:

```bash
# Expect failure without a production API base (by design):
# npm run build

# Simulate Vercel env, then build:
set NEXT_PUBLIC_API_BASE=https://your-api.up.railway.app
npm run build
npm run start
```

On macOS/Linux use `export NEXT_PUBLIC_API_BASE=...` instead of `set`.

## Production smoke-test checklist

Run against the **Vercel production URL** with Railway live:

- [ ] Site loads over HTTPS
- [ ] Browser Network tab: API calls go to Railway, **not** `127.0.0.1`
- [ ] No CORS errors in the console
- [ ] No mixed-content warnings
- [ ] Paste a public YouTube URL → job starts (`queued` / `processing`)
- [ ] Processing stages update (`downloading` → … → `creating_clips`) when backend sends `stage`
- [ ] Job completes → clip list appears
- [ ] Preview plays a vertical clip
- [ ] Download saves an MP4
- [ ] Refresh mid-job restores polling (until a Railway restart)
- [ ] Mobile (Safari): preview + download work

## Rollback

1. **Vercel:** Deployments → open previous successful deploy → **Promote to Production** (Instant Rollback).
2. **Bad env var:** Fix `NEXT_PUBLIC_API_BASE` in Vercel → **Redeploy** (required; public env is build-time).
3. **CORS mistake:** Restore previous `CORS_ORIGINS` on Railway → restart service. Frontend unchanged.
4. **Emergency:** Unpublish / take project offline in Vercel until Railway is healthy.

## Out of scope

- UI redesign
- Backend feature changes
- Auth / credits (later sprints)
