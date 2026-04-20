# Use a Python 3.10 slim image to keep the footprint low
FROM python:3.10-slim

# Step 1: System Level Dependencies
# ffmpeg and libsndfile1 are critical for librosa/soundfile
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Step 2: Python Dependencies
# We copy ONLY requirements.txt first to cache the pip install layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 3: Bake the Whisper Model
# This is the "7/7" step that usually fails. 
# We do this BEFORE copying the rest of the code.
RUN python -c "import whisper; whisper.load_model('small')"

# Step 4: Application Code
# Since your code changes most often, this is the final layer.
COPY . .

# Expose FastAPI port
EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
