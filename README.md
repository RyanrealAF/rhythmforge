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

- Endpoint: `R2_ENDPOINT` *(or `CLOUDFLARE_R2_ENDPOINT`)*
- Access key: `R2_ACCESS_KEY` *(or `R2_ACCESS_KEY_ID` / `AWS_ACCESS_KEY_ID`)*
- Secret key: `R2_SECRET_KEY` *(or `R2_SECRET_ACCESS_KEY` / `AWS_SECRET_ACCESS_KEY` / `R2_key` / `R2_KEY`)*
- Optional combined key format: `R2_KEY="<access_key>:<secret_key>"`
- Bucket: `R2_BUCKET` *(or `CLOUDFLARE_R2_BUCKET`; optional, defaults to `rhythmforge-stems`)*

If these are not set, the app still runs with local temp-file processing.

## Notes for Hugging Face builds

The Docker image intentionally does **not** pre-download Whisper during build. Whisper is downloaded lazily at runtime on the first vocal-analysis request to avoid HF builder failures caused by external model fetches during image build.
