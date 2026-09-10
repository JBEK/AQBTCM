import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import find_peaks, lfilter
import sounddevice as sd


def _crossfade_loop(clip, fade_samples):
    """Fond la fin d'un signal dans son début, pour qu'il boucle sans à-coup."""
    fade_samples = min(fade_samples, len(clip) // 4)
    if fade_samples <= 0:
        return clip
    clip = clip.astype(np.float64).copy()
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = 1 - fade_in
    if clip.ndim == 2:
        fade_in = fade_in[:, None]
        fade_out = fade_out[:, None]
    head = clip[:fade_samples]
    tail = clip[-fade_samples:]
    clip[-fade_samples:] = tail * fade_out + head * fade_in
    return clip


class HeartbeatSonifier:
    """
    Génère un son CONTINU (pas de clip court répété) sur toute la durée de
    l'enregistrement ECG, dont le volume suit exactement la courbe (avec
    normalisation locale + clipping des valeurs extrêmes) et superpose des
    "booms" sur les transitoires rapides. Joue en flux audio streamé,
    en arrière-plan, sans coupure.

    Usage minimal :
        sonifier = HeartbeatSonifier("JFD_01.txt")
        sonifier.start()   # non bloquant
        ...
        sonifier.stop()
    """

    def __init__(self, ecg_file, max_duration_s=None,
                 vol_min=0.15, vol_max=1.0, roll_window_s=1.5,
                 clip_percentile=2,          # contraint les valeurs extrêmes (%)
                 base_freq=110.0, detune_cents=7,
                 boom_percentile=90, boom_min_distance_s=0.05,
                 boom_duration_s=0.12, boom_gain=0.5,
                 loop_fade_ms=200):
        self.ecg_file = ecg_file
        self.max_duration_s = max_duration_s
        self.vol_min = vol_min
        self.vol_max = vol_max
        self.roll_window_s = roll_window_s
        self.clip_percentile = clip_percentile
        self.base_freq = base_freq
        self.detune_cents = detune_cents
        self.boom_percentile = boom_percentile
        self.boom_min_distance_s = boom_min_distance_s
        self.boom_duration_s = boom_duration_s
        self.boom_gain = boom_gain
        self.loop_fade_ms = loop_fade_ms

        self._audio_float = None
        self._framerate = 44100
        self._n_channels = 1
        self._play_pos = 0
        self._stream = None

    # ---------------- rendu (calculé une seule fois) ----------------
    def _render(self):
        framerate = self._framerate
        n_channels = self._n_channels

        with open(self.ecg_file, "r") as f:
            rows = [line.strip().split(",") for line in f if line.strip()]
            raw_data = np.array([int(r[0]) for r in rows], dtype=np.float64)
            timestamps_us = np.array([int(r[1]) for r in rows], dtype=np.int64)

        if len(raw_data) == 0:
            raise ValueError(f"Fichier '{self.ecg_file}' vide.")

        t_rel = (timestamps_us - timestamps_us[0]) / 1_000_000.0
        if self.max_duration_s is not None:
            mask = t_rel <= self.max_duration_s
            raw_data = raw_data[mask]
            t_rel = t_rel[mask]

        duration = t_rel[-1] if len(t_rel) > 0 else 0
        if duration == 0:
            raise ValueError("Pas de données à sonifier.")
        sample_rate_hz = len(raw_data) / duration

        # --- contrainte des valeurs extrêmes (le gros pic ne dicte plus tout) ---
        lo, hi = np.percentile(raw_data, [self.clip_percentile, 100 - self.clip_percentile])
        raw_c = np.clip(raw_data, lo, hi)

        # --- enveloppe locale (fenêtre glissante, garde les reliefs fins) ---
        window = int(self.roll_window_s * sample_rate_hz)
        if window % 2 == 0:
            window += 1
        window = max(window, 3)
        pad = window // 2
        padded = np.pad(raw_c, pad, mode="edge")
        windows = sliding_window_view(padded, window)
        roll_min, roll_max = windows.min(axis=1), windows.max(axis=1)
        roll_range = np.maximum(roll_max - roll_min, 1e-6)
        env_norm = (raw_c - roll_min) / roll_range
        env_scaled = self.vol_min + (self.vol_max - self.vol_min) * env_norm

        # --- transitoires ("boom"), calculés sur les valeurs contraintes aussi ---
        diff = np.diff(raw_c, prepend=raw_c[0])
        diff_smooth = np.convolve(diff, np.ones(3) / 3, mode="same")
        thresh = np.percentile(diff_smooth, self.boom_percentile)
        boom_idx, _ = find_peaks(
            diff_smooth, height=thresh,
            distance=max(1, int(self.boom_min_distance_s * sample_rate_hz))
        )
        boom_times = t_rel[boom_idx]
        boom_strength = diff_smooth[boom_idx]
        boom_strength = boom_strength / (boom_strength.max() + 1e-9)

        # --- synthèse CONTINUE sur toute la durée (pas de boucle courte) ---
        total_frames = int(duration * framerate)
        t_audio = np.arange(total_frames) / framerate

        f0 = self.base_freq
        f1 = f0 * (2 ** (self.detune_cents / 1200))
        tone = (np.sin(2 * np.pi * f0 * t_audio)
                + np.sin(2 * np.pi * f1 * t_audio)
                + 0.35 * np.sin(2 * np.pi * (f0 / 2) * t_audio))

        # léger souffle filtré (texture organique), filtre IIR peu coûteux
        rng = np.random.default_rng(42)
        noise = rng.normal(0, 1, total_frames)
        noise = lfilter([0.02], [1, -0.98], noise)
        noise = noise / (np.max(np.abs(noise)) + 1e-9)
        tone = tone + 0.06 * noise
        tone = tone / (np.max(np.abs(tone)) + 1e-9) * 0.7

        # --- enveloppe interpolée sur la grille audio, appliquée à la synthèse ---
        envelope_audio = np.interp(t_audio, t_rel, env_scaled)
        final = (tone * envelope_audio * 32767)[:, None]  # mono -> (N, 1)

        # --- booms superposés, fondu de sortie pour ne jamais couper net ---
        boom_len = int(self.boom_duration_s * framerate)
        bt = np.arange(boom_len) / framerate
        boom_freq = 45 + (150 - 45) * np.exp(-bt * 18)
        boom_phase = 2 * np.pi * np.cumsum(boom_freq) / framerate
        boom_shape = np.sin(boom_phase) * np.exp(-bt * 14)
        tail_fade = int(0.015 * framerate)
        if 0 < tail_fade < boom_len:
            boom_shape[-tail_fade:] *= np.linspace(1, 0, tail_fade)
        boom_shape /= np.max(np.abs(boom_shape)) + 1e-9

        for bt_time, strength in zip(boom_times, boom_strength):
            start = int(bt_time * framerate)
            end = min(start + boom_len, total_frames)
            seg_len = end - start
            if seg_len <= 0:
                continue
            burst = boom_shape[:seg_len] * strength * self.boom_gain * 32767
            final[start:end, 0] += burst

        peak = np.max(np.abs(final))
        if peak > 32000:
            final *= 32000 / peak

        # un seul point de bouclage, à l'échelle de la piste entière
        loop_fade_samples = int(self.loop_fade_ms / 1000 * framerate)
        final = _crossfade_loop(final, loop_fade_samples)

        self._audio_float = (final / 32768.0).astype(np.float32)
        self._play_pos = 0
        print(f"[HeartbeatSonifier] Rendu prêt : {duration:.1f}s continues, "
              f"{len(boom_idx)} booms détectés")

    # ---------------- flux audio continu (jamais réouvert) ----------------
    def _callback(self, outdata, frames, time_info, status):
        if status:
            print(status)
        pcm = self._audio_float
        n = len(pcm)
        idx = (self._play_pos + np.arange(frames)) % n
        outdata[:] = pcm[idx]
        self._play_pos = (self._play_pos + frames) % n

    def start(self):
        if self._audio_float is None:
            self._render()
        self._stream = sd.OutputStream(
            samplerate=self._framerate,
            channels=self._n_channels,
            dtype="float32",
            callback=self._callback,
            blocksize=1024,
        )
        self._stream.start()

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


# ============================================================
# Exemple d'intégration dans un script d'installation plus large
# ============================================================
if __name__ == "__main__":
    import time

    sonifier = HeartbeatSonifier("JFD_01.txt")
    sonifier.start()

    try:
        print("Sonification en fond, continue. Ctrl+C pour arrêter.")
        while True:
            # ... reste de ton installation ...
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sonifier.stop()