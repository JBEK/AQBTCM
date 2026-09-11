"""
Petite fenêtre de réglage pour HeartbeatSonifier (play_heartbeat.py).

Chaque slider relâché relance un rendu sur un extrait court (par défaut
12s de JFD_01.txt) et le joue en boucle en direct, pour entendre l'effet
du réglage tout de suite. Le bouton "Valider ces réglages" écrit les
valeurs choisies dans heartbeat_settings.json, à reporter ensuite dans
play_heartbeat.py une fois qu'on est content du son.

Usage :
    python heartbeat_tuner.py
"""
import json
import tkinter as tk
from tkinter import ttk

from play_heartbeat import HeartbeatSonifier

ECG_FILE = "JFD_01.txt"
PREVIEW_DURATION_S = 12
SETTINGS_FILE = "heartbeat_settings.json"

# (clé, label, min, max, valeur par défaut, nb de décimales)
PARAMS = {
    "Tonalité": [
        ("root_freq", "Note de base (Hz)", 80, 220, 130.81, 1),
        ("fifth_gain", "Présence de la quinte", 0.0, 1.0, 0.45, 2),
        ("octave_gain", "Présence de l'octave", 0.0, 1.0, 0.25, 2),
        ("third_gain", "Présence de la tierce", 0.0, 1.0, 0.0, 2),
        ("third_interval_cents", "Couleur tierce (300=mineure, 400=majeure)", 250, 450, 400, 0),
        ("vibrato_hz", "Vitesse du vibrato (Hz)", 0.0, 1.0, 0.12, 2),
        ("vibrato_cents", "Profondeur du vibrato (cents)", 0, 20, 3, 0),
        ("chorus_width", "Choeur (épaisseur)", 0.0, 1.0, 0.0, 2),
    ],
    "Souffle": [
        ("noise_level", "Niveau du souffle", 0.0, 0.15, 0.035, 3),
        ("noise_cutoff_hz", "Couleur du souffle (Hz)", 100, 2000, 600, 0),
    ],
    "Battements": [
        ("boom_gain", "Intensité des battements", 0.0, 3.0, 0.32, 2),
        ("boom_duration_s", "Durée d'un battement (s)", 0.05, 0.4, 0.22, 2),
        ("boom_attack_s", "Rondeur de l'attaque (s)", 0.0, 0.1, 0.02, 3),
        ("boom_pitch", "Fréquence de base (Hz)", 30, 150, 55, 0),
        ("boom_sweep", "Ampleur de la glissade (Hz)", 0, 150, 35, 0),
        ("boom_warmth", "Chaleur (étouffé)", 0.0, 1.0, 0.0, 2),
        ("boom_percentile", "Sensibilité de détection", 50, 99, 90, 0),
    ],
    "Dynamique": [
        ("vol_min", "Volume minimum", 0.0, 0.5, 0.25, 2),
        ("vol_max", "Volume maximum", 0.5, 1.0, 0.9, 2),
        ("bed_gain", "Volume du fond", 0.0, 1.5, 1.0, 2),
        ("playback_speed", "Vitesse de lecture (1=normal)", 0.2, 2.0, 1.0, 2),
        ("roll_window_s", "Réactivité à l'ECG (s)", 0.2, 5.0, 1.5, 2),
        ("master_volume", "Volume général", 0.0, 1.5, 1.0, 2),
        ("brightness", "Clarté (étouffé/ouvert)", 0.0, 1.0, 1.0, 2),
        ("stereo_width", "Largeur stéréo", 0.0, 1.0, 0.0, 2),
    ],
    "Echo": [
        ("echo_delay_s", "Temps (s)", 0.05, 0.6, 0.28, 2),
        ("echo_feedback", "Feedback", 0.0, 0.8, 0.35, 2),
        ("echo_repeats", "Répétitions", 1, 10, 5, 0),
        ("echo_mix", "Mix", 0.0, 1.0, 0.0, 2),
    ],
    "Delay": [
        ("delay_delay_s", "Temps (s)", 0.02, 0.3, 0.12, 2),
        ("delay_feedback", "Feedback", 0.0, 0.8, 0.45, 2),
        ("delay_repeats", "Répétitions", 1, 20, 10, 0),
        ("delay_mix", "Mix", 0.0, 1.0, 0.0, 2),
    ],
    "Reverb": [
        ("reverb_size", "Taille de l'espace", 0.1, 2.0, 0.5, 2),
        ("reverb_decay_s", "Durée de traîne (s)", 0.2, 3.0, 1.2, 2),
        ("reverb_mix", "Mix", 0.0, 1.0, 0.0, 2),
    ],
}


BASE_DEFAULTS = {
    key: default
    for section in PARAMS.values()
    for key, label, lo, hi, default, decimals in section
}


def _load_saved_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


class TunerApp:
    def __init__(self, root):
        self.root = root
        root.title("Réglage du son du coeur")

        self.vars = {}
        self.value_labels = {}
        self.current_sonifier = None
        self.saved_settings = _load_saved_settings()
        self.undo_stack = []
        self.pre_drag_snapshot = None
        root.bind_all("<Control-z>", self._undo)

        columns = tk.Frame(root)
        columns.pack(padx=10, pady=10, fill="both", expand=True)
        left = tk.Frame(columns)
        right = tk.Frame(columns)
        left.grid(row=0, column=0, sticky="n", padx=(0, 20))
        right.grid(row=0, column=1, sticky="n")

        left_sections = ["Tonalité", "Souffle", "Battements", "Dynamique"]
        right_sections = ["Echo", "Delay", "Reverb"]
        for section in left_sections:
            self._build_section(left, section)
        for section in right_sections:
            self._build_section(right, section)

        controls = tk.Frame(root)
        controls.pack(pady=10)
        self.play_button = tk.Button(controls, text="Jouer", command=self.toggle_play)
        self.play_button.grid(row=0, column=0, padx=5)
        tk.Button(controls, text="Valider ces réglages", command=self.validate).grid(row=0, column=1, padx=5)
        tk.Button(controls, text="Réinitialiser (son de base)", command=self.reset_to_base).grid(row=0, column=2, padx=5)
        tk.Button(controls, text="Charger derniers réglages enregistrés",
                  command=self.load_saved).grid(row=0, column=3, padx=5)

        self.status = tk.Label(root, text="Prêt.", anchor="w")
        self.status.pack(fill="x", padx=10, pady=(0, 10))

        self.playing = False

    def _build_section(self, parent, section):
        frame = ttk.LabelFrame(parent, text=section)
        frame.pack(fill="x", pady=5)
        for key, label, lo, hi, default, decimals in PARAMS[section]:
            default = self.saved_settings.get(key, default)
            row = tk.Frame(frame)
            row.pack(fill="x", padx=5, pady=2)
            tk.Label(row, text=label, width=26, anchor="w").pack(side="left")
            var = tk.DoubleVar(value=default)
            self.vars[key] = var
            value_label = tk.Label(row, text=self._fmt(default, decimals), width=6)
            value_label.pack(side="right")
            self.value_labels[key] = (value_label, decimals)
            scale = ttk.Scale(row, from_=lo, to=hi, variable=var, orient="horizontal",
                               command=lambda v, k=key: self._on_move(k))
            scale.pack(side="left", fill="x", expand=True, padx=5)
            scale.bind("<ButtonPress-1>", lambda e: self._on_press())
            scale.bind("<ButtonRelease-1>", lambda e: self._on_release())

    def _fmt(self, value, decimals):
        return f"{value:.{decimals}f}"

    def _on_move(self, key):
        value = self.vars[key].get()
        label, decimals = self.value_labels[key]
        label.config(text=self._fmt(value, decimals))

    def _on_press(self):
        self.pre_drag_snapshot = self._current_kwargs()

    def _on_release(self):
        if self.pre_drag_snapshot is not None:
            if self._current_kwargs() != self.pre_drag_snapshot:
                self.undo_stack.append(self.pre_drag_snapshot)
                del self.undo_stack[:-50]  # limite l'historique
            self.pre_drag_snapshot = None
        if self.playing:
            self._update_playing()

    def _undo(self, event=None):
        if not self.undo_stack:
            self.status.config(text="Rien à annuler.")
            return
        snapshot = self.undo_stack.pop()
        self._apply_settings(snapshot)
        if self.playing:
            self._update_playing()
        else:
            self.status.config(text="Réglages précédents restaurés (Ctrl+Z).")

    def _apply_settings(self, settings):
        for key, value in settings.items():
            if key in self.vars:
                self.vars[key].set(value)
                self._on_move(key)

    def reset_to_base(self):
        self.undo_stack.append(self._current_kwargs())
        del self.undo_stack[:-50]
        self._apply_settings(BASE_DEFAULTS)
        if self.playing:
            self._update_playing()
        else:
            self.status.config(text="Réinitialisé au son de base.")

    def load_saved(self):
        settings = _load_saved_settings()
        if not settings:
            self.status.config(text=f"Pas de {SETTINGS_FILE} à charger.")
            return
        self.undo_stack.append(self._current_kwargs())
        del self.undo_stack[:-50]
        self._apply_settings(settings)
        if self.playing:
            self._update_playing()
        else:
            self.status.config(text=f"Derniers réglages enregistrés chargés depuis {SETTINGS_FILE}.")

    def _current_kwargs(self):
        int_keys = {"echo_repeats", "delay_repeats"}
        return {k: (int(v.get()) if k in int_keys else v.get()) for k, v in self.vars.items()}

    def _update_playing(self):
        """Recalcule le buffer sur le flux déjà ouvert, sans jamais le
        couper : pas de silence/à-coup entre deux réglages."""
        self.status.config(text="Mise à jour...")
        self.root.update_idletasks()
        self.current_sonifier.update_params(**self._current_kwargs())
        self.status.config(text=f"Lecture en boucle ({PREVIEW_DURATION_S}s d'extrait).")

    def toggle_play(self):
        if self.playing:
            self.current_sonifier.stop()
            self.playing = False
            self.play_button.config(text="Jouer")
            self.status.config(text="Arrêté.")
        else:
            if self.current_sonifier is None:
                self.current_sonifier = HeartbeatSonifier(ECG_FILE, max_duration_s=PREVIEW_DURATION_S)
            self.current_sonifier.update_params(**self._current_kwargs())
            self.current_sonifier.start()
            self.playing = True
            self.play_button.config(text="Arrêter")
            self.status.config(text=f"Lecture en boucle ({PREVIEW_DURATION_S}s d'extrait).")

    def validate(self):
        settings = self._current_kwargs()
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        self.status.config(text=f"Réglages enregistrés dans {SETTINGS_FILE}.")


if __name__ == "__main__":
    root = tk.Tk()
    app = TunerApp(root)
    root.mainloop()
    if app.current_sonifier is not None:
        app.current_sonifier.stop()
