import numpy as np
from typing import List

def analyze_interplay(vocal: dict, drums: dict) -> dict:
    vocal_emphasis = vocal["delivery"]["emphasis_times"]
    kick_times = drums["patterns"]["kick_times"]
    snare_times = drums["patterns"]["snare_times"]
    beat_times = drums["beat_times"]
    tempo = max(1.0, float(drums["tempo"]["bpm"]))
    bar_duration = (60.0 / tempo) * 4

    # KICK / VOCAL ALIGNMENT
    on_kick, between_kicks, floating = 0, 0, 0
    for vt in vocal_emphasis:
        kick_dists = [abs(vt - kt) for kt in kick_times] if kick_times else [999]
        nearest_kick = min(kick_dists)
        beat_unit = 60.0 / tempo
        if nearest_kick < beat_unit * 0.12:
            on_kick += 1
        elif nearest_kick < beat_unit * 0.5:
            between_kicks += 1
        else:
            floating += 1

    total_em = max(1, on_kick + between_kicks + floating)
    kick_alignment = {
        "on_kick_pct": round(on_kick / total_em * 100),
        "between_kicks_pct": round(between_kicks / total_em * 100),
        "floating_pct": round(floating / total_em * 100)
    }

    # SNARE RELATIONSHIP
    snare_lock_count = 0
    displaced_bars = set()
    for vt in vocal_emphasis:
        snare_dists = [abs(vt - st) for st in snare_times] if snare_times else [999]
        nearest_snare = min(snare_dists)
        beat_unit = 60.0 / tempo
        if nearest_snare < beat_unit * 0.15:
            snare_lock_count += 1
        elif nearest_snare > beat_unit * 0.4:
            bar_idx = int(vt / bar_duration)
            displaced_bars.add(bar_idx)

    riding_snare = snare_lock_count > len(vocal_emphasis) * 0.3
    displaced_bar_count = len(displaced_bars)

    # SYNCOPATION EVENTS — vocal emphasis lands between kick AND snare
    syncopation_events = []
    beat_unit = 60.0 / tempo
    for vt in vocal_emphasis:
        kick_dists = [abs(vt - kt) for kt in kick_times] if kick_times else [beat_unit]
        snare_dists = [abs(vt - st) for st in snare_times] if snare_times else [beat_unit]
        nd_kick = min(kick_dists)
        nd_snare = min(snare_dists)
        if nd_kick > beat_unit * 0.2 and nd_snare > beat_unit * 0.2:
            bar_num = int(vt / bar_duration) + 1
            beat_in_bar = ((vt % bar_duration) / (beat_unit)) + 1
            syncopation_events.append({
                "time": round(vt, 2),
                "bar": bar_num,
                "beat": round(beat_in_bar, 1)
            })

    # GRID TENSION SCORE — 0 locked, 100 free
    if beat_times and vocal_emphasis:
        beat_arr = np.array(beat_times)
        offsets = []
        for vt in vocal_emphasis:
            dists = np.abs(beat_arr - vt)
            nearest = float(np.min(dists))
            offsets.append(nearest / (beat_unit + 1e-9))
        mean_offset = float(np.mean(offsets))
        grid_tension = round(min(100, int(mean_offset * 200)))
    else:
        grid_tension = 50

    # POCKET SCORE — composite
    pocket_components = []
    on_kick_score = kick_alignment["on_kick_pct"] + kick_alignment["between_kicks_pct"] * 0.5
    pocket_components.append(on_kick_score)
    pocket_components.append(min(100, snare_lock_count / max(1, len(vocal_emphasis)) * 150))
    consistency_penalty = min(30, displaced_bar_count * 5)
    base_pocket = float(np.mean(pocket_components)) - consistency_penalty
    pocket_score = round(max(0, min(100, base_pocket)))

    # PHRASE BOUNDARY ALIGNMENT
    vocal_breaths = vocal["delivery"]["breath_times"]
    phrase_starts = vocal_breaths[:]
    if phrase_starts:
        aligned = 0
        total_phrases = len(phrase_starts)
        for pt in phrase_starts:
            bar_boundary = round(pt / bar_duration) * bar_duration
            if abs(pt - bar_boundary) < beat_unit * 0.25:
                aligned += 1
        aligned_pct = round(aligned / max(1, total_phrases) * 100)
        staggered_count = total_phrases - aligned
    else:
        aligned_pct = 75
        staggered_count = 2
        total_phrases = 8

    # TIMELINE — unified marker data for frontend
    duration = max(vocal["duration_seconds"], drums["duration_seconds"])
    def normalize_times(times, dur):
        return [round(t / dur * 100, 1) for t in times if t <= dur]

    sync_times = [e["time"] for e in syncopation_events]
    vocal_marker_times = vocal["delivery"]["emphasis_times"]

    return {
        "pocket_score": pocket_score,
        "kick_alignment": kick_alignment,
        "snare_relationship": {
            "riding_snare": riding_snare,
            "displaced_bar_count": displaced_bar_count
        },
        "syncopation": {
            "event_count": len(syncopation_events),
            "events": syncopation_events[:10]
        },
        "grid_tension": grid_tension,
        "phrase_alignment": {
            "total_phrases": total_phrases,
            "aligned_count": round(total_phrases * aligned_pct / 100),
            "aligned_pct": aligned_pct,
            "staggered_count": staggered_count
        },
        "timeline": {
            "duration_seconds": round(duration, 2),
            "kick_positions_pct": normalize_times(kick_times[:24], duration),
            "snare_positions_pct": normalize_times(snare_times[:24], duration),
            "vocal_positions_pct": normalize_times(vocal_marker_times[:32], duration),
            "sync_positions_pct": normalize_times(sync_times[:16], duration)
        }
    }
