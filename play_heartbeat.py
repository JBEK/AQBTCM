import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import find_peaks, butter, lfilter
import sounddevice as sd


def _tap_repeats(signal, framerate, delay_s, feedback, n_repeats, mix):
    """Ajoute n_repeats copies retardées et décroissantes du signal (base
    commune à echo/delay/reverb : seuls temps/feedback/nb de répétitions
    changent)."""
    if mix <= 0 or n_repeats <= 0 or delay_s <= 0:
        return signal
    delay_samples = int(delay_s * framerate)
    if delay_samples <= 0:
        return signal
    wet = np.zeros_like(signal)
    gain = 1.0
    for i in range(1, n_repeats + 1):
        gain *= feedback
        shift = delay_samples * i
        if shift >= len(signal) or gain < 1e-3:
            break
        wet[shift:] += signal[:-shift] * gain
    return signal + mix * wet


def _apply_echo(signal, framerate, delay_s, feedback, repeats, mix):
    """Répétitions espacées et distinctes."""
    return _tap_repeats(signal, framerate, delay_s, feedback, repeats, mix)


def _apply_delay(signal, framerate, delay_s, feedback, repeats, mix):
    """Répétitions rapprochées et denses (traînée rythmique)."""
    return _tap_repeats(signal, framerate, delay_s, feedback, repeats, mix)


def _apply_reverb(signal, framerate, size, decay_s, mix):
    """Reverb algorithmique légère : plusieurs 'combs' à temps premiers
    entre eux, sommés, pour un effet diffus sans convolution ni impulse
    response (peu coûteux, adapté au réglage interactif)."""
    if mix <= 0:
        return signal
    base_delays_ms = [29, 37, 41, 53]
    wet = np.zeros_like(signal)
    for ms in base_delays_ms:
        delay_s = (ms / 1000.0) * max(size, 0.05)
        feedback = np.exp(-3 * delay_s / max(decay_s, 0.05))
        repeats = int(decay_s / max(delay_s, 1e-3)) + 1
        wet = wet + _tap_repeats(signal, framerate, delay_s, feedback, repeats, 1.0) - signal
    wet /= len(base_delays_ms)
    return signal + mix * wet


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
                 vol_min=0.25, vol_max=0.9, bed_gain=1.0, roll_window_s=1.5,
                 playback_speed=1.0,  # 1.0=vitesse d'origine, <1 ralentit les battements
                 clip_percentile=2,          # contraint les valeurs extrêmes (%)
                 root_freq=130.81,           # C3 : accord chaud (fondamentale+quinte+octave)
                 fifth_gain=0.45, octave_gain=0.25,
                 third_gain=0.0, third_interval_cents=400,  # 400=tierce majeure, 300=mineure
                 vibrato_hz=0.12, vibrato_cents=3,
                 chorus_width=0.0,
                 noise_level=0.035, noise_cutoff_hz=600,
                 boom_percentile=90, boom_min_distance_s=0.05,
                 boom_duration_s=0.22, boom_gain=0.52, boom_attack_s=0.02,
                 boom_pitch=55, boom_sweep=35, boom_warmth=0.0,
                 echo_delay_s=0.28, echo_feedback=0.35, echo_repeats=5, echo_mix=0.0,
                 delay_delay_s=0.12, delay_feedback=0.45, delay_repeats=10, delay_mix=0.0,
                 reverb_size=0.5, reverb_decay_s=1.2, reverb_mix=0.0,
                 brightness=1.0, master_volume=1.0, stereo_width=0.0,
                 loop_fade_ms=200):
        self.ecg_file = ecg_file
        self.max_duration_s = max_duration_s
        self.vol_min = vol_min
        self.vol_max = vol_max
        self.bed_gain = bed_gain
        self.playback_speed = playback_speed
        self.roll_window_s = roll_window_s
        self.clip_percentile = clip_percentile
        self.root_freq = root_freq
        self.fifth_gain = fifth_gain
        self.octave_gain = octave_gain
        self.third_gain = third_gain
        self.third_interval_cents = third_interval_cents
        self.vibrato_hz = vibrato_hz
        self.vibrato_cents = vibrato_cents
        self.chorus_width = chorus_width
        self.noise_level = noise_level
        self.noise_cutoff_hz = noise_cutoff_hz
        self.boom_percentile = boom_percentile
        self.boom_min_distance_s = boom_min_distance_s
        self.boom_duration_s = boom_duration_s
        self.boom_gain = boom_gain
        self.boom_attack_s = boom_attack_s
        self.boom_pitch = boom_pitch
        self.boom_sweep = boom_sweep
        self.boom_warmth = boom_warmth
        self.echo_delay_s = echo_delay_s
        self.echo_feedback = echo_feedback
        self.echo_repeats = echo_repeats
        self.echo_mix = echo_mix
        self.delay_delay_s = delay_delay_s
        self.delay_feedback = delay_feedback
        self.delay_repeats = delay_repeats
        self.delay_mix = delay_mix
        self.reverb_size = reverb_size
        self.reverb_decay_s = reverb_decay_s
        self.reverb_mix = reverb_mix
        self.brightness = brightness
        self.master_volume = master_volume
        self.stereo_width = stereo_width
        self.loop_fade_ms = loop_fade_ms

        self._audio_float = None
        self._framerate = 44100
        self._n_channels = 2
        self._play_pos = 0
        self._stream = None

        # enveloppe control-rate (0-1, avant mise à l'échelle vol_min/vol_max),
        # exposée pour piloter des LEDs en phase avec le son sans dupliquer le
        # calcul d'enveloppe (voir get_current_envelope)
        self._env_times = None
        self._env_norm = None
        self._duration = 0.0

    # ---------------- rendu (calculé une seule fois) ----------------
    def _render(self):
        framerate = self._framerate

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

        self._env_times = t_rel
        self._env_norm = env_norm
        self._duration = duration

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
        # playback_speed ralentit/accélère uniquement le déroulé de l'ECG
        # (enveloppe + placement des battements), pas la hauteur du son
        speed = max(self.playback_speed, 0.05)
        total_frames = int((duration / speed) * framerate)
        t_audio = np.arange(total_frames) / framerate

        # accord chaud (fondamentale + quinte + octave + tierce optionnelle)
        # + vibrato lent, plutôt qu'un battement de 2 notes proches (effet
        # "moniteur d'hôpital")
        vibrato = 1 + (self.vibrato_cents / 1200) * np.sin(2 * np.pi * self.vibrato_hz * t_audio)
        f_root = self.root_freq * vibrato
        f_fifth = self.root_freq * 1.5 * vibrato
        f_octave = self.root_freq * 2.0 * vibrato
        f_third = self.root_freq * (2 ** (self.third_interval_cents / 1200)) * vibrato
        phase_root = 2 * np.pi * np.cumsum(f_root) / framerate
        phase_fifth = 2 * np.pi * np.cumsum(f_fifth) / framerate
        phase_octave = 2 * np.pi * np.cumsum(f_octave) / framerate
        phase_third = 2 * np.pi * np.cumsum(f_third) / framerate
        core = (1.0 * np.sin(phase_root)
                + self.fifth_gain * np.sin(phase_fifth)
                + self.octave_gain * np.sin(phase_octave)
                + self.third_gain * np.sin(phase_third))

        # choeur : 2 voix légèrement désaccordées, dérive lente indépendante,
        # panoramiquées pour donner de la largeur (avec stereo_width)
        if self.chorus_width > 0:
            detune_cents = 4 + 10 * self.chorus_width
            lfo_l = np.sin(2 * np.pi * 0.07 * t_audio + 0.6)
            lfo_r = np.sin(2 * np.pi * 0.11 * t_audio + 2.1)
            f_chorus_l = self.root_freq * (2 ** ((detune_cents * lfo_l) / 1200))
            f_chorus_r = self.root_freq * (2 ** ((-detune_cents * lfo_r) / 1200))
            chorus_l = 0.35 * self.chorus_width * np.sin(2 * np.pi * np.cumsum(f_chorus_l) / framerate)
            chorus_r = 0.35 * self.chorus_width * np.sin(2 * np.pi * np.cumsum(f_chorus_r) / framerate)
        else:
            chorus_l = chorus_r = np.zeros(total_frames)

        # souffle : bruit lissé passe-bas (vagues/respiration, pas de "hiss") ;
        # un flux indépendant pour le canal droit permet de décorréler L/R
        # quand stereo_width > 0
        rng = np.random.default_rng(42)
        b, a = butter(2, self.noise_cutoff_hz / (framerate / 2), btype="low")
        noise_l = lfilter(b, a, rng.normal(0, 1, total_frames))
        noise_l = noise_l / (np.max(np.abs(noise_l)) + 1e-9)
        if self.stereo_width > 0:
            rng2 = np.random.default_rng(43)
            noise_r_indep = lfilter(b, a, rng2.normal(0, 1, total_frames))
            noise_r_indep = noise_r_indep / (np.max(np.abs(noise_r_indep)) + 1e-9)
            noise_r = (1 - self.stereo_width) * noise_l + self.stereo_width * noise_r_indep
        else:
            noise_r = noise_l

        tone_l = core + chorus_l + self.noise_level * noise_l
        tone_r = core + chorus_r + self.noise_level * noise_r
        peak_tone = max(np.max(np.abs(tone_l)), np.max(np.abs(tone_r))) + 1e-9
        tone_l = tone_l / peak_tone * 0.75
        tone_r = tone_r / peak_tone * 0.75

        # --- enveloppe interpolée sur la grille audio, appliquée à la synthèse ---
        envelope_audio = np.interp(t_audio * speed, t_rel, env_scaled)
        bed_l = tone_l * envelope_audio * 32767 * self.bed_gain
        bed_r = tone_r * envelope_audio * 32767 * self.bed_gain

        # saturation douce (tanh) appliquée au FOND seul : le nivelle/chauffe
        # avant d'ajouter les booms, pour que boom_gain ne soit plus écrasé
        # par le même compresseur (sinon augmenter boom_gain ne se
        # traduisait presque plus par un battement plus fort à l'oreille)
        def _warm(s):
            normalized = s / 32767.0
            return np.tanh(normalized * 1.15) / np.tanh(1.15) * 32000

        sig_l, sig_r = _warm(bed_l), _warm(bed_r)

        # --- booms superposés APRES la saturation du fond (centrés,
        # identiques sur les deux canaux) : battement feutré (attaque
        # arrondie, pas de clic), filtré par boom_warmth pour un rendu plus
        # ou moins étouffé ---
        boom_len = int(self.boom_duration_s * framerate)
        bt = np.arange(boom_len) / framerate
        boom_freq = self.boom_pitch + self.boom_sweep * np.exp(-bt * 10)
        boom_phase = 2 * np.pi * np.cumsum(boom_freq) / framerate
        decay = np.exp(-bt * 9)
        attack_len = max(1, int(self.boom_attack_s * framerate))
        attack = np.ones(boom_len)
        attack[:attack_len] = np.linspace(0, 1, attack_len) ** 2
        boom_shape = np.sin(boom_phase) * decay * attack
        if self.boom_warmth > 0:
            warmth_cutoff = 4000 - self.boom_warmth * 3700
            bb, ba = butter(2, min(warmth_cutoff, framerate / 2 - 1) / (framerate / 2), btype="low")
            boom_shape = lfilter(bb, ba, boom_shape)
        tail_fade = int(0.03 * framerate)
        if 0 < tail_fade < boom_len:
            boom_shape[-tail_fade:] *= np.linspace(1, 0, tail_fade)
        boom_shape /= np.max(np.abs(boom_shape)) + 1e-9

        for bt_time, strength in zip(boom_times, boom_strength):
            start = int((bt_time / speed) * framerate)
            end = min(start + boom_len, total_frames)
            seg_len = end - start
            if seg_len <= 0:
                continue
            burst = boom_shape[:seg_len] * strength * self.boom_gain * 32767
            sig_l[start:end] += burst
            sig_r[start:end] += burst

        # --- effets (echo / delay / reverb), tous à mix=0 par défaut ---
        for apply_fx, args in (
            (_apply_echo, (self.echo_delay_s, self.echo_feedback, self.echo_repeats, self.echo_mix)),
            (_apply_delay, (self.delay_delay_s, self.delay_feedback, self.delay_repeats, self.delay_mix)),
            (_apply_reverb, (self.reverb_size, self.reverb_decay_s, self.reverb_mix)),
        ):
            sig_l = apply_fx(sig_l, framerate, *args)
            sig_r = apply_fx(sig_r, framerate, *args)

        # --- tonalité générale (brightness) et volume global ---
        brightness_cutoff = min(300 + self.brightness * 5700, framerate / 2 - 1)
        bb, ba = butter(2, brightness_cutoff / (framerate / 2), btype="low")
        sig_l = lfilter(bb, ba, sig_l) * self.master_volume
        sig_r = lfilter(bb, ba, sig_r) * self.master_volume

        peak = max(np.max(np.abs(sig_l)), np.max(np.abs(sig_r)))
        if peak > 32000:
            sig_l *= 32000 / peak
            sig_r *= 32000 / peak
        sig_l = np.clip(sig_l, -32768, 32767)
        sig_r = np.clip(sig_r, -32768, 32767)

        # toujours stéréo (2 canaux identiques si stereo_width == 0) : le flux
        # audio garde un nombre de canaux fixe, ce qui permet de le laisser
        # ouvert en continu et de changer les réglages sans jamais le couper
        self._n_channels = 2
        final = np.stack([sig_l, sig_r], axis=1)

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

    def get_current_envelope(self):
        """Enveloppe (0-1) à l'instant actuel du flux audio, en phase avec ce
        qui est en train de jouer — pour piloter des LEDs en même temps que le
        son (AQBTCM : interruption battement de cœur)."""
        if self._env_times is None or self._duration <= 0:
            return 0.0
        speed = max(self.playback_speed, 0.05)
        t_ecg = (self._play_pos / self._framerate) * speed
        t_ecg_wrapped = t_ecg % self._duration
        return float(np.interp(t_ecg_wrapped, self._env_times, self._env_norm))

    def update_params(self, **kwargs):
        """Change des réglages et re-rend le buffer à la volée, sans jamais
        arrêter le flux audio : le callback continue de lire l'ancien buffer
        pendant le calcul, puis bascule sur le nouveau d'un coup, sans coupure."""
        for key, value in kwargs.items():
            setattr(self, key, value)
        self._render()

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