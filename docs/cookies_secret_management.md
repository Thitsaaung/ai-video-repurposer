# YouTube cookies — secret management

Short ops guide for T-Clipper. Cookie **loading and downloader behaviour are unchanged**; this document describes how to keep Netscape cookies out of git and how to use them safely locally and on Railway.

---

## What changed

| Control | Detail |
|---------|--------|
| `.gitignore` | Ignores `*cookies*.txt` (and `yt_cookies_*.txt`), with an allowlist for `*cookies.example.txt` |
| Template | `backend/cookies.example.txt` — format + setup comments only, no real sessions |
| Docs | README + `.env.example` point at this workflow |

Code still resolves cookies only via env:

1. `YOUTUBE_COOKIES_FILE` (path must exist)
2. else `YOUTUBE_COOKIES_BASE64` (materialized to a temp file)
3. else no cookies

There is **no hardcoded** `cookies.txt` path in the downloader or config.

---

## Local development

1. Copy the template:
   ```powershell
   cd backend
   Copy-Item cookies.example.txt cookies.txt
   ```
2. Replace `backend/cookies.txt` with a real Netscape export (dedicated Google account recommended).
3. In `backend/.env` or repo-root `.env`:
   ```env
   YOUTUBE_COOKIES_FILE=cookies.txt
   ```
   Run uvicorn / `python -m services.*` from `backend/` so the relative path resolves. Absolute paths are fine too.
4. Confirm git will not stage secrets:
   ```powershell
   git check-ignore -v backend/cookies.txt
   ```
   You should see a `.gitignore` rule. `backend/cookies.example.txt` must **not** be ignored.

Never commit `cookies.txt`, `extension_cookies.txt`, or base64 cookie blobs.

---

## Railway (production)

1. Keep cookies on your machine only (`backend/cookies.txt` stays local / gitignored).
2. Base64-encode the file and set **service variable** `YOUTUBE_COOKIES_BASE64` on the backend (Root Directory `backend/`).
3. Do **not** set `YOUTUBE_COOKIES_FILE` to a repo path on Railway unless you intentionally mount a secret file outside git.
4. When bot / “sign in” errors return, re-export cookies, update `YOUTUBE_COOKIES_BASE64`, restart/redeploy.

No Railway config files were changed for this task.

---

## Verify accidental-commit protection

```powershell
# Real cookie file — must be ignored
git check-ignore -v backend/cookies.txt

# Attempt to add should not stage it (path is ignored)
git add -n backend/cookies.txt

# Example template — must be trackable
git check-ignore -v backend/cookies.example.txt
git add -n backend/cookies.example.txt
```

---

## If cookies were ever committed

1. Rotate the Google/YouTube session (sign out other sessions / change password as appropriate).
2. Remove the file from git history if it reached a remote (ops incident — treat as credential leak).
3. Re-export fresh cookies into the local gitignored file / Railway `YOUTUBE_COOKIES_BASE64` only.
