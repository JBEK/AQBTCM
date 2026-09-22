"""
Rendu OFFLINE d'une sonification "douce" du coeur, vers un fichier .wav.

Objectif : proposer une alternative moins clinique/glaçante à la nappe
grave detunee + boom perçant de play_heartbeat.py. Ici :
  - accord chaud (fondamentale + quinte + octave) au lieu d'un battement
    de deux notes très proches (qui donnait cet effet "moniteur d'hopital").
  - vibrato lent et discret plutôt qu'un battement audio permanent.
  - souffle filtré passe-bas doux (façon vagues/respiration) au lieu d'un
    bruit plus rêche.
  - "boum" du coeur avec attaque arrondie (pas de clic net) et descente
    plus lente : un battement feutré, pas un impact.

Usage :
    python render_heartbeat_doux.py            # -> hearty_doux.wav (piste entière)
    python render_heartbeat_doux.py --duration 20   # -> aperçu de 20s
"""
import argparse

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import find_peaks, butter, lfilter
from scipy.io import wavfile


def play_wav(path):
    """Joue un .wav directement sur les haut-parleurs (bloquant)."""
    import sounddevice as sd
    rate, data = wavfile.read(path)
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    sd.play(data, rate)
    sd.wait()


def render_comforting(ecg_file, out_wav, max_duration_s=None,
                       framerate=44100,
                       vol_min=0.25, vol_max=0.9, roll_window_s=1.5,
                       clip_percentile=2,
                       root_freq=130.81,          # C3, chaud sans etre trop grave
                       vibrato_hz=0.12, vibrato_cents=3,
                       noise_level=0.035, noise_cutoff_hz=600,
                       boom_percentile=90, boom_min_distance_s=0.05,
                       boom_duration_s=0.22, boom_gain=0.32,
                       boom_attack_s=0.02):
    with open(ecg_file, "r") as f:
        rows = [line.strip().split(",") for line in f if line.strip()]
        raw_data = np.array([int(r[0]) for r in rows], dtype=np.float64)
        timestamps_us = np.array([int(r[1]) for r in rows], dtype=np.int64)

    if len(raw_data) == 0:
        raise ValueError(f"Fichier '{ecg_file}' vide.")

    t_rel = (timestamps_us - timestamps_us[0]) / 1_000_000.0
    if max_duration_s is not None:
        mask = t_rel <= max_duration_s
        raw_data = raw_data[mask]
        t_rel = t_rel[mask]

    duration = t_rel[-1] if len(t_rel) > 0 else 0
    if duration == 0:
        raise ValueError("Pas de données à sonifier.")
    sample_rate_hz = len(raw_data) / duration

    # --- contrainte des valeurs extrêmes ---
    lo, hi = np.percentile(raw_data, [clip_percentile, 100 - clip_percentile])
    raw_c = np.clip(raw_data, lo, hi)

    # --- enveloppe locale ---
    window = int(roll_window_s * sample_rate_hz)
    if window % 2 == 0:
        window += 1
    window = max(window, 3)
    pad = window // 2
    padded = np.pad(raw_c, pad, mode="edge")
    windows = sliding_window_view(padded, window)
    roll_min, roll_max = windows.min(axis=1), windows.max(axis=1)
    roll_range = np.maximum(roll_max - roll_min, 1e-6)
    env_norm = (raw_c - roll_min) / roll_range
    env_scaled = vol_min + (vol_max - vol_min) * env_norm

    # --- transitoires (pour placer les "boums") ---
    diff = np.diff(raw_c, prepend=raw_c[0])
    diff_smooth = np.convolve(diff, np.ones(3) / 3, mode="same")
    thresh = np.percentile(diff_smooth, boom_percentile)
    boom_idx, _ = find_peaks(
        diff_smooth, height=thresh,
        distance=max(1, int(boom_min_distance_s * sample_rate_hz))
    )
    boom_times = t_rel[boom_idx]
    boom_strength = diff_smooth[boom_idx]
    boom_strength = boom_strength / (boom_strength.max() + 1e-9)

    total_frames = int(duration * framerate)
    t_audio = np.arange(total_frames) / framerate

    # --- accord chaud (fondamentale + quinte + octave) + vibrato lent ---
    vibrato = 1 + (vibrato_cents / 1200) * np.sin(2 * np.pi * vibrato_hz * t_audio)
    f_root = root_freq * vibrato
    f_fifth = root_freq * 1.5 * vibrato
    f_octave = root_freq * 2.0 * vibrato

    phase_root = 2 * np.pi * np.cumsum(f_root) / framerate
    phase_fifth = 2 * np.pi * np.cumsum(f_fifth) / framerate
    phase_octave = 2 * np.pi * np.cumsum(f_octave) / framerate

    tone = (1.0 * np.sin(phase_root)
            + 0.45 * np.sin(phase_fifth)
            + 0.25 * np.sin(phase_octave))

    # --- souffle : bruit lissé passe-bas (vagues/respiration, pas de "hiss") ---
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 1, total_frames)
    b, a = butter(2, noise_cutoff_hz / (framerate / 2), btype="low")
    noise = lfilter(b, a, noise)
    noise = noise / (np.max(np.abs(noise)) + 1e-9)
    tone = tone + noise_level * noise
    tone = tone / (np.max(np.abs(tone)) + 1e-9) * 0.75

    # --- enveloppe ECG appliquée à la synthèse ---
    envelope_audio = np.interp(t_audio, t_rel, env_scaled)
    final = (tone * envelope_audio * 32767)[:, None]

    # --- "boums" feutrés : attaque arrondie, descente douce, pas de clic ---
    boom_len = int(boom_duration_s * framerate)
    bt = np.arange(boom_len) / framerate
    boom_freq = 55 + (90 - 55) * np.exp(-bt * 10)
    boom_phase = 2 * np.pi * np.cumsum(boom_freq) / framerate
    decay = np.exp(-bt * 9)
    attack_len = max(1, int(boom_attack_s * framerate))
    attack = np.ones(boom_len)
    attack[:attack_len] = np.linspace(0, 1, attack_len) ** 2  # arrondi, pas de clic
    boom_shape = np.sin(boom_phase) * decay * attack
    tail_fade = int(0.03 * framerate)
    if 0 < tail_fade < boom_len:
        boom_shape[-tail_fade:] *= np.linspace(1, 0, tail_fade)
    boom_shape /= np.max(np.abs(boom_shape)) + 1e-9

    for bt_time, strength in zip(boom_times, boom_strength):
        start = int(bt_time * framerate)
        end = min(start + boom_len, total_frames)
        seg_len = end - start
        if seg_len <= 0:
            continue
        burst = boom_shape[:seg_len] * strength * boom_gain * 32767
        final[start:end, 0] += burst

    # --- saturation douce (tanh) pour un rendu "chaud" plutôt qu'un clip dur ---
    normalized = final[:, 0] / 32767.0
    warmed = np.tanh(normalized * 1.15) / np.tanh(1.15)
    final_i16 = np.clip(warmed * 32000, -32768, 32767).astype(np.int16)

    wavfile.write(out_wav, framerate, final_i16)
    print(f"[render_heartbeat_doux] {out_wav} : {duration:.1f}s, "
          f"{len(boom_idx)} battements détectés")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecg", default="JFD_01.txt")
    parser.add_argument("--out", default="hearty_doux.wav")
    parser.add_argument("--duration", type=float, default=None,
                         help="durée max en secondes (par défaut : piste entière)")
    parser.add_argument("--play", action="store_true",
                         help="joue le fichier sur les haut-parleurs juste après le rendu")
    args = parser.parse_args()

    render_comforting(args.ecg, args.out, max_duration_s=args.duration)

    if args.play:
        print(f"[render_heartbeat_doux] lecture de {args.out}...")
        play_wav(args.out)
