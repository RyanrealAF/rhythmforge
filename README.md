---
title: RhythmForge
emoji: 🥁
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# RhythmForge (Hugging Face Space)

This Space runs the RhythmForge FastAPI app using the included `Dockerfile`.

## Runtime

- Entry server: `uvicorn app:app --host 0.0.0.0 --port 7860`
- UI route: `/` (served from `index.html`)
- Health route: `/health` (includes startup diagnostics for `index.html` presence and R2 env completeness)

## Required secrets (optional for R2 integration)

Set these in **Space Settings → Variables and secrets** if you want Cloudflare R2 uploads:

- `R2_ENDPOINT`
- `R2_ACCESS_KEY`
- `R2_SECRET_KEY`
- `R2_BUCKET` (optional, defaults to `rhythmforge-stems`)

If these are not set, the app still runs with local temp-file processing.
