# T-Clipper frontend (Next.js)

**Production deploy:** see [DEPLOY.md](./DEPLOY.md) (Vercel Root Directory = `frontend`, Railway CORS, env vars, smoke tests).

Local env template: [`.env.example`](./.env.example).

---

## Getting Started

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

`NEXT_PUBLIC_API_BASE` defaults to `http://127.0.0.1:8000` in development only.

## Production build (local check)

```bash
# PowerShell
$env:NEXT_PUBLIC_API_BASE = "https://your-api.up.railway.app"
npm run build
npm run start
```

Production builds **require** a non-localhost HTTPS `NEXT_PUBLIC_API_BASE`.

## Deploy on Vercel

Follow **[DEPLOY.md](./DEPLOY.md)** end-to-end.
