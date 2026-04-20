import os
import tempfile
import logging

import boto3
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from vocal import analyze_vocal
from drums import analyze_drums
from interplay import analyze_interplay

app = FastAPI(title="RhythmForge")
logger = logging.getLogger("rhythmforge")

STARTUP_DIAGNOSTICS = {
    "index_html_found": False,
    "r2_enabled": False,
    "missing_r2_vars": [],
    "r2_var_sources": {}
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif"}


def _env_first(*names: str) -> tuple[str, str]:
    for name in names:
        value = os.environ.get(name, "")
        if value:
            return value, name
    return "", names[0]


def _parse_combined_r2_key(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    for delim in (":", "|", ","):
        if delim in value:
            left, right = value.split(delim, 1)
            return left.strip(), right.strip()
    return "", ""


# ENTRY POINT: Cloudflare R2 config — set via HF Space secrets
R2_ENDPOINT, R2_ENDPOINT_SOURCE = _env_first("R2_ENDPOINT", "CLOUDFLARE_R2_ENDPOINT")
R2_ACCESS_KEY, R2_ACCESS_KEY_SOURCE = _env_first("R2_ACCESS_KEY", "R2_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID")
R2_SECRET_KEY, R2_SECRET_KEY_SOURCE = _env_first("R2_SECRET_KEY", "R2_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY")

# Optional convenience format: R2_KEY="<access_key>:<secret_key>"
# Also supports legacy single-secret usage: R2_key / R2_KEY as secret only.
R2_COMBINED_KEY, R2_COMBINED_KEY_SOURCE = _env_first("R2_KEY", "R2_key")
combined_access, combined_secret = _parse_combined_r2_key(R2_COMBINED_KEY)
if combined_access and combined_secret:
    if not R2_ACCESS_KEY:
        R2_ACCESS_KEY = combined_access
        R2_ACCESS_KEY_SOURCE = f"{R2_COMBINED_KEY_SOURCE}(access)"
    if not R2_SECRET_KEY:
        R2_SECRET_KEY = combined_secret
        R2_SECRET_KEY_SOURCE = f"{R2_COMBINED_KEY_SOURCE}(secret)"
elif R2_COMBINED_KEY and not R2_SECRET_KEY:
    R2_SECRET_KEY = R2_COMBINED_KEY
    R2_SECRET_KEY_SOURCE = R2_COMBINED_KEY_SOURCE

R2_BUCKET, R2_BUCKET_SOURCE = _env_first("R2_BUCKET", "CLOUDFLARE_R2_BUCKET")
if not R2_BUCKET:
    R2_BUCKET = "rhythmforge-stems"
    R2_BUCKET_SOURCE = "default"

USE_R2 = all([R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY])


@app.on_event("startup")
async def startup_checks() -> None:
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    index_exists = os.path.exists(html_path)

    required_r2_vars = {
        "R2_ENDPOINT": bool(R2_ENDPOINT),
        "R2_ACCESS_KEY": bool(R2_ACCESS_KEY),
        "R2_SECRET_KEY": bool(R2_SECRET_KEY),
    }
    missing_r2 = [name for name, present in required_r2_vars.items() if not present]

    STARTUP_DIAGNOSTICS["index_html_found"] = index_exists
    STARTUP_DIAGNOSTICS["r2_enabled"] = USE_R2
    STARTUP_DIAGNOSTICS["missing_r2_vars"] = missing_r2
    STARTUP_DIAGNOSTICS["r2_var_sources"] = {
        "endpoint": R2_ENDPOINT_SOURCE,
        "access_key": R2_ACCESS_KEY_SOURCE,
        "secret_key": R2_SECRET_KEY_SOURCE,
        "bucket": R2_BUCKET_SOURCE,
    }

    logger.info(
        "Startup checks: index_html_found=%s r2_enabled=%s",
        index_exists,
        USE_R2
    )
    if missing_r2:
        logger.info("Optional R2 vars missing (expected unless R2 enabled): %s", ", ".join(missing_r2))


def get_r2():
    if not USE_R2:
        return None
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto"
    )


def validate_audio_upload(upload: UploadFile) -> None:
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext or 'unknown'}'. Allowed: {sorted(ALLOWED_AUDIO_EXTENSIONS)}"
        )


async def save_temp(upload: UploadFile) -> str:
    validate_audio_upload(upload)
    suffix = os.path.splitext(upload.filename or "")[-1] or ".wav"
    data = await upload.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(data)
        return f.name


def safe_unlink(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r") as f:
        return f.read()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "r2_enabled": USE_R2,
        "startup": STARTUP_DIAGNOSTICS
    }


@app.post("/analyze/vocal")
async def route_vocal(file: UploadFile = File(...)):
    path = await save_temp(file)
    try:
        result = analyze_vocal(path)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        safe_unlink(path)


@app.post("/analyze/drums")
async def route_drums(file: UploadFile = File(...)):
    path = await save_temp(file)
    try:
        result = analyze_drums(path)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        safe_unlink(path)


@app.post("/analyze/full")
async def route_full(
    vocal_file: UploadFile = File(...),
    drum_file: UploadFile = File(...)
):
    vpath = await save_temp(vocal_file)
    dpath = await save_temp(drum_file)
    try:
        vocal_result = analyze_vocal(vpath)
        drum_result = analyze_drums(dpath)
        interplay_result = analyze_interplay(vocal_result, drum_result)
        return JSONResponse({
            "vocal": vocal_result,
            "drums": drum_result,
            "interplay": interplay_result
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        safe_unlink(vpath)
        safe_unlink(dpath)
