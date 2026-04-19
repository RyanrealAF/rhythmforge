# ENTRY POINT: RhythmForge FastAPI backend
import os, tempfile, json, boto3
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from vocal import analyze_vocal
from drums import analyze_drums
from interplay import analyze_interplay

app = FastAPI(title="RhythmForge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ENTRY POINT: Cloudflare R2 config — set via HF Space secrets
R2_ENDPOINT    = os.environ.get("R2_ENDPOINT", "")
R2_ACCESS_KEY  = os.environ.get("R2_ACCESS_KEY", "")
R2_SECRET_KEY  = os.environ.get("R2_SECRET_KEY", "")
R2_BUCKET      = os.environ.get("R2_BUCKET", "rhythmforge-stems")
USE_R2         = all([R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY])

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

def save_temp(upload: UploadFile) -> str:
    suffix = os.path.splitext(upload.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(upload.file.read())
        return f.name

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r") as f:
        return f.read()

@app.get("/health")
async def health():
    return {"status": "ok", "r2_enabled": USE_R2}

@app.post("/analyze/vocal")
async def route_vocal(file: UploadFile = File(...)):
    path = save_temp(file)
    try:
        result = analyze_vocal(path)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(path)

@app.post("/analyze/drums")
async def route_drums(file: UploadFile = File(...)):
    path = save_temp(file)
    try:
        result = analyze_drums(path)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(path)

@app.post("/analyze/full")
async def route_full(
    vocal_file: UploadFile = File(...),
    drum_file: UploadFile = File(...)
):
    vpath = save_temp(vocal_file)
    dpath = save_temp(drum_file)
    try:
        vocal_result = analyze_vocal(vpath)
        drum_result  = analyze_drums(dpath)
        interplay_result = analyze_interplay(vocal_result, drum_result)
        return JSONResponse({
            "vocal":     vocal_result,
            "drums":     drum_result,
            "interplay": interplay_result
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(vpath)
        os.unlink(dpath)
