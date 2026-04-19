import librosa
import numpy as np
import whisper
import soundfile as sf
import tempfile, os

_whisper_model = None

def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model("small")
    return _whisper_model

def analyze_vocal(audio_path: str) -> dict:
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    # TEMPO + BEAT GRID
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    bar_duration = (60.0 / float(tempo)) * 4

    # ONSET DETECTION — proxy for syllable transients
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units='frames', backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # SYLLABLE DENSITY PER BAR
    num_bars = max(1, int(duration / bar_duration))
    syllables_per_bar = []
    for i in range(num_bars):
        bar_start = i * bar_duration
        bar_end = bar_start + bar_duration
        count = int(np.sum((onset_times >= bar_start) & (onset_times < bar_end)))
        syllables_per_bar.append(count)

    avg_density = float(np.mean(syllables_per_bar)) if syllables_per_bar else 0
    peak_density = int(np.max(syllables_per_bar)) if syllables_per_bar else 0

    # EMPHASIS — top 20% onset strength events
    onset_strength = librosa.onset.onset_strength(y=y, sr=sr)
    strength_at_onsets = onset_strength[onset_frames] if len(onset_frames) > 0 else np.array([])
    threshold = float(np.percentile(strength_at_onsets, 80)) if len(strength_at_onsets) > 0 else 0
    emphasis_frames = onset_frames[strength_at_onsets >= threshold] if len(strength_at_onsets) > 0 else []
    emphasis_times = librosa.frames_to_time(emphasis_frames, sr=sr).tolist()

    # BREATH DETECTION — low energy regions between phrases
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    silence_threshold = float(np.percentile(rms, 15))
    breath_regions = []
    in_silence = False
    silence_start = 0.0
    for t, r in zip(rms_times, rms):
        if r < silence_threshold and not in_silence:
            in_silence = True
            silence_start = float(t)
        elif r >= silence_threshold and in_silence:
            in_silence = False
            duration_s = float(t) - silence_start
            if 0.1 < duration_s < 0.8:
                breath_regions.append(round(silence_start, 2))
    breath_points = breath_regions[:12]

    # DRY/WET RATIO — high-freq tail energy as reverb proxy
    S = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    high_freq_mask = freqs > 4000
    total_energy = float(np.mean(S))
    tail_energy = float(np.mean(S[high_freq_mask, :])) if np.any(high_freq_mask) else 0
    wet_ratio = min(0.45, round(tail_energy / (total_energy + 1e-9), 2))
    dry_ratio = round(1.0 - wet_ratio, 2)

    # DOUBLE/SHADOW VOCAL — spectral flux anomaly
    spectral_flux = np.mean(np.diff(S, axis=1) ** 2)
    shadow_detected = bool(spectral_flux > np.percentile(np.diff(S, axis=1) ** 2, 85))

    # DRUM BLEED — low frequency energy in vocal stem
    low_freq_mask = freqs < 200
    low_energy = float(np.mean(S[low_freq_mask, :])) if np.any(low_freq_mask) else 0
    bleed_ratio = low_energy / (total_energy + 1e-9)
    drum_bleed = "detected" if bleed_ratio > 0.12 else "clean"

    # WHISPER — word-level timing for syllable accuracy
    whisper_model = get_whisper()
    result = whisper_model.transcribe(audio_path, word_timestamps=True, language="en")
    word_timings = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            word_timings.append({
                "word": w.get("word", "").strip(),
                "start": round(float(w.get("start", 0)), 2),
                "end": round(float(w.get("end", 0)), 2)
            })

    # FLOW PATTERN — triplet vs straight detection via onset spacing
    if len(onset_times) > 3:
        gaps = np.diff(onset_times)
        beat_unit = 60.0 / float(tempo) / 4
        ratios = gaps / (beat_unit + 1e-9)
        triplet_score = float(np.mean(np.abs(ratios - 1.5) < 0.2))
        double_time_score = float(np.mean(ratios < 0.6))
        syncopated_score = float(np.mean((ratios > 0.6) & (ratios < 0.9)))
        if double_time_score > 0.3:
            flow_pattern = "double-time sections"
        elif triplet_score > 0.25:
            flow_pattern = "triplet-based"
        elif syncopated_score > 0.3:
            flow_pattern = "syncopated 16ths"
        else:
            flow_pattern = "straight 16ths"
    else:
        flow_pattern = "insufficient data"

    # RHYTHMIC PLACEMENT vs beat grid
    if len(beat_times) > 1 and len(onset_times) > 0:
        beat_unit = float(np.mean(np.diff(beat_times)))
        offsets = []
        for ot in onset_times:
            diffs = np.abs(beat_times - ot)
            nearest = float(np.min(diffs))
            offsets.append(nearest / beat_unit)
        mean_offset = float(np.mean(offsets))
        if mean_offset < 0.1:
            placement = "on the beat"
        elif mean_offset < 0.2:
            placement = "in pocket"
        else:
            placement = "behind the beat"
    else:
        placement = "unknown"

    double_time_bars = int(np.sum(np.array(syllables_per_bar) > avg_density * 1.6))

    return {
        "flow": {
            "pattern": flow_pattern,
            "placement": placement,
            "double_time_bar_count": double_time_bars
        },
        "syllable_density": {
            "avg_per_bar": round(avg_density, 1),
            "peak_bar": peak_density,
            "per_bar": syllables_per_bar
        },
        "delivery": {
            "emphasis_hit_count": len(emphasis_times),
            "emphasis_times": [round(t, 2) for t in emphasis_times[:20]],
            "breath_point_count": len(breath_points),
            "breath_times": breath_points,
            "shadow_vocal_detected": shadow_detected,
            "double_time_bar_count": double_time_bars
        },
        "signal": {
            "dry_ratio": dry_ratio,
            "wet_ratio": wet_ratio,
            "drum_bleed": drum_bleed
        },
        "word_timings": word_timings,
        "tempo_bpm": round(float(tempo), 1),
        "duration_seconds": round(duration, 2)
    }
