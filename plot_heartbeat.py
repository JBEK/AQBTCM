"""Visuel rapide d'un fichier ECG brut (format value,timestamp_us par ligne).

Usage :
    python plot_heartbeat.py JFD_01.txt
    python plot_heartbeat.py            # utilise INES_02.txt par défaut
"""
import sys

import numpy as np
import matplotlib.pyplot as plt

ecg_file = sys.argv[1] if len(sys.argv) > 1 else "INES_02.txt"

with open(ecg_file) as f:
    rows = [line.strip().split(",") for line in f if line.strip()]
raw_data = np.array([int(r[0]) for r in rows], dtype=np.float64)
timestamps_us = np.array([int(r[1]) for r in rows], dtype=np.int64)
t_rel = (timestamps_us - timestamps_us[0]) / 1_000_000.0

plt.figure(figsize=(14, 5))
plt.plot(t_rel, raw_data, lw=0.6, color="#333")
plt.title(f"{ecg_file} — signal brut ({t_rel[-1]:.1f}s, {len(raw_data)} échantillons)")
plt.xlabel("Temps (s)")
plt.ylabel("Valeur brute")
plt.tight_layout()
plt.show()
