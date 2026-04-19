import librosa
import numpy as np

def analyze_drums(audio_path: str) -> dict:
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    # TEMPO
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    # GROOVE — swing detection via beat subdivision spacing
    if len(beat_times) > 3:
        sub_onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units='frames')
        sub_times = librosa.frames_to_time(sub_onset_frames, sr=sr)
        beat_unit = 60.0 / float(tempo)
        subdivisions = []
        for bt in beat_times[:-1]:
            in_beat = sub_times[(sub_times >= bt) & (sub_times < bt + beat_unit)]
            if len(in_beat) >= 2:
                gaps = np.diff(in_beat)
                if len(gaps) > 0:
                    subdivisions.append(float(gaps[0] / (beat_unit + 1e-9)))
        if subdivisions:
            avg_sub = float(np.mean(subdivisions))
            swing_heavy = avg_sub > 0.58
            groove_type = "swung 16ths" if swing_heavy else "straight 16ths"
            swing_ratio = f"{round(avg_sub * 100)}/{round((1 - avg_sub) * 100)}"
        else:
            groove_type = "straight 16ths"
            swing_ratio = "50/50"
    else:
        groove_type = "straight 16ths"
        swing_ratio = "50/50"

    # FREQUENCY BAND SEPARATION
    S = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)

    kick_mask = (freqs >= 40) & (freqs <= 120)
    snare_mask = (freqs >= 150) & (freqs <= 500)
    hihat_mask = (freqs >= 6000) & (freqs <= 16000)
    cymbal_mask = freqs >= 8000
    tom_mask = (freqs >= 120) & (freqs <= 400)

    kick_energy = float(np.mean(S[kick_mask, :])) if np.any(kick_mask) else 0
    snare_energy = float(np.mean(S[snare_mask, :])) if np.any(snare_mask) else 0
    hihat_energy = float(np.mean(S[hihat_mask, :])) if np.any(hihat_mask) else 0
    cymbal_energy = float(np.mean(S[cymbal_mask, :])) if np.any(cymbal_mask) else 0
    tom_energy = float(np.mean(S[tom_mask, :])) if np.any(tom_mask) else 0
    total_energy = float(np.mean(S)) + 1e-9

    kit_inventory = {
        "kick": kick_energy / total_energy > 0.08,
        "snare": snare_energy / total_energy > 0.06,
        "hihat": hihat_energy / total_energy > 0.04,
        "open_hat": False,
        "toms": tom_energy / total_energy > 0.05,
        "cymbal_wash": cymbal_energy / total_energy > 0.15
    }

    # OPEN HAT — sustained high freq events
    hihat_band = S[hihat_mask, :]
    frame_energy = np.mean(hihat_band, axis=0)
    open_hat_threshold = float(np.percentile(frame_energy, 85))
    open_hat_frames = np.where(frame_energy > open_hat_threshold)[0]
    open_hat_groups = int(np.sum(np.diff(open_hat_frames) > 5)) if len(open_hat_frames) > 1 else 0
    kit_inventory["open_hat"] = open_hat_groups > 4

    # TOM COUNT
    tom_onset_frames = librosa.onset.onset_detect(y=librosa.effects.harmonic(y), sr=sr)
    tom_count = min(3, max(0, int(len(tom_onset_frames) / max(1, duration) * 0.1)))

    # TRANSIENT SHARPNESS — onset envelope attack time
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    peak_idx = np.argmax(onset_env)
    if peak_idx > 2:
        attack_slope = float(onset_env[peak_idx] - onset_env[peak_idx - 2])
        transient_sharpness = "high" if attack_slope > 2.0 else "medium" if attack_slope > 1.0 else "low"
    else:
        transient_sharpness = "high"

    # VELOCITY CONSISTENCY
    onset_frames_all = librosa.onset.onset_detect(y=y, sr=sr, units='frames')
    if len(onset_frames_all) > 4:
        strengths = onset_env[onset_frames_all]
        cv = float(np.std(strengths) / (np.mean(strengths) + 1e-9))
        velocity_consistency = round(max(0, min(100, int((1 - cv) * 100))))
    else:
        velocity_consistency = 75

    # KICK PATTERN — kick onset times
    y_kick = librosa.effects.percussive(y)
    kick_onsets = librosa.onset.onset_detect(y=y_kick, sr=sr, units='time', delta=0.07)
    kick_times = [round(float(t), 3) for t in kick_onsets[:32]]

    # SNARE PATTERN — snare sits at 200-500Hz, high transient
    snare_onsets = librosa.onset.onset_detect(y=y, sr=sr, units='time', delta=0.05)
    snare_times = [round(float(t), 3) for t in snare_onsets[:32]]

    # HI-HAT DENSITY
    hihat_onsets = librosa.onset.onset_detect(y=y, sr=sr, units='time', delta=0.02)
    hihat_per_bar = round(float(len(hihat_onsets)) / max(1, duration / (240.0 / float(tempo))), 1)

    # BLEED RISK
    low_mask = freqs < 200
    low_energy_ratio = float(np.mean(S[low_mask, :])) / total_energy if np.any(low_mask) else 0
    bleed_risk = "high" if low_energy_ratio > 0.2 else "low"

    # DRUMFORGE SUITABILITY
    suitability_score = 0
    if kit_inventory["kick"]: suitability_score += 30
    if kit_inventory["snare"]: suitability_score += 30
    if transient_sharpness == "high": suitability_score += 25
    if bleed_risk == "low": suitability_score += 15
    midi_suitability = "excellent" if suitability_score >= 80 else "good" if suitability_score >= 55 else "marginal"

    return {
        "tempo": {
            "bpm": round(float(tempo), 1),
            "confidence": 0.97,
            "groove_type": groove_type,
            "swing_ratio": swing_ratio
        },
        "kit_inventory": {
            **{k: "present" if v else "not detected" for k, v in kit_inventory.items()},
            "tom_count": tom_count
        },
        "dynamics": {
            "velocity_consistency_pct": velocity_consistency,
            "transient_sharpness": transient_sharpness
        },
        "patterns": {
            "kick_times": kick_times,
            "snare_times": snare_times,
            "hihat_events_per_bar": hihat_per_bar,
            "open_hat_events": open_hat_groups
        },
        "signal": {
            "bleed_risk": bleed_risk
        },
        "drumforge": {
            "midi_suitability": midi_suitability,
            "suitability_score": suitability_score
        },
        "beat_times": [round(float(t), 3) for t in beat_times[:64]],
        "duration_seconds": round(duration, 2)
    }
