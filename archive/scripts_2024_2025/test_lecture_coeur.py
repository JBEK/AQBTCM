import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

filename = "JFD_01.txt"

try:
    with open(filename, "r") as f:
        rows = [line.strip().split(",") for line in f if line.strip()]
        raw_data = np.array([int(r[0]) for r in rows], dtype=np.float32)
        timestamps_us = np.array([int(r[1]) for r in rows], dtype=np.int64)
    if len(raw_data) == 0:
        print(f"⚠️ Fichier '{filename}' vide.")
        exit()
except FileNotFoundError:
    print(f"❌ Fichier '{filename}' introuvable.")
    exit()
except (IndexError, ValueError):
    print("❌ Format inattendu. Attendu : 'valeur,timestamp_us' par ligne.")
    exit()

# Temps relatif de chaque échantillon, en secondes depuis le début de l'enregistrement
t_rel = (timestamps_us - timestamps_us[0]) / 1_000_000.0
duration = t_rel[-1]
avg_hz = len(raw_data) / duration if duration > 0 else 0
print(f"Durée enregistrement : {duration:.2f} s — {len(raw_data)} échantillons "
      f"(~{avg_hz:.1f} Hz)")

WINDOW_SIZE = 600  # points affichés à l'écran (fenêtre glissante)
WINDOW_DURATION = WINDOW_SIZE / avg_hz if avg_hz > 0 else 3.0

fig, ax = plt.subplots(figsize=(10, 4))
fig.canvas.manager.set_window_title(f"ECG Vitesse Réelle — {filename}")

(line,) = ax.plot(np.arange(WINDOW_SIZE), np.full(WINDOW_SIZE, 2048), color="#E6007E", linewidth=1.2)
ax.set_ylim(-100, 4200)
ax.set_xlim(0, WINDOW_SIZE)
ax.set_title(f"Relecture calée sur le temps réel : {filename}", fontsize=11)
ax.set_ylabel("ADC (12-bit)")
ax.grid(True, linestyle="--", alpha=0.3)

playback_start = None  # perf_counter() au premier frame

def update(frame):
    global playback_start
    now = time.perf_counter()
    if playback_start is None:
        playback_start = now

    # Position dans l'enregistrement en fonction du temps réel écoulé
    # depuis le début de la lecture (et non du nombre de frames rendues) :
    # ça garde le bon rythme même si matplotlib redessine plus lentement
    # que la cadence d'échantillonnage.
    elapsed = (now - playback_start) % duration  # boucle en revenant au début
    idx = np.searchsorted(t_rel, elapsed)
    idx = min(idx, len(raw_data) - 1)

    start = max(0, idx - WINDOW_SIZE + 1)
    window = raw_data[start:idx + 1]
    if len(window) < WINDOW_SIZE:
        # début de fichier : on complète à gauche avec la première valeur
        pad = np.full(WINDOW_SIZE - len(window), raw_data[0])
        window = np.concatenate([pad, window])

    line.set_ydata(window)
    return (line,)

# interval = fréquence de rafraîchissement visuel, PAS la cadence des données.
# 20 ms (~50 Hz) est un bon compromis fluidité/charge CPU ; la fonction
# update() se charge de resynchroniser sur le temps réel à chaque appel.
ani = animation.FuncAnimation(
    fig, update, interval=20, blit=True, cache_frame_data=False
)

plt.tight_layout()
plt.show()