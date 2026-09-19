"""Point d'entrée unique de l'installation AQBTCM (2026).

Une seule fenêtre Tkinter : des boutons de test pour vérifier chaque mode
indépendamment (lumières, perceuses, fumée, battement de cœur), et un bouton
pour lancer l'installation complète. Toute la logique matérielle vit dans
aqbtcm_engine.Installation - ce fichier ne fait que l'afficher et appeler ses
méthodes.
"""

import threading
import tkinter as tk
from tkinter import messagebox

from aqbtcm_engine import Installation

FONT_NORMAL = ("Helvetica", 10)
FONT_BOLD = ("Helvetica", 10, "bold")

install = Installation()
drill_running = {0: False, 1: False, 2: False}


def run_action(fn, *args):
    """Relance une action en tâche de fond, en levant d'abord un éventuel
    stop_flag posé par un arrêt d'urgence ou une interruption précédente."""
    install.stop_flag.clear()
    threading.Thread(target=fn, args=args, daemon=True).start()


# ---------------- connexion ----------------
def connecter():
    def _connect():
        lights_ok, motors_ok = install.connect()
        lbl_lights.config(text=f"LIGHTS: {'OK' if lights_ok else 'absent'}")
        lbl_motors.config(text=f"MOTORS: {'OK' if motors_ok else 'absent'}")

    threading.Thread(target=_connect, daemon=True).start()


# ---------------- perceuses (boutons individuels) ----------------
def toggle_drill(drill_id, btn):
    if drill_running[drill_id]:
        install.drill_stop(drill_id)
        drill_running[drill_id] = False
        btn.config(text=f"Perceuse {drill_id + 1} : démarrer")
    else:
        install.drill_start(drill_id)
        drill_running[drill_id] = True
        btn.config(text=f"Perceuse {drill_id + 1} : arrêter")


# ---------------- arrêt d'urgence ----------------
def arret_urgence():
    install.arret_urgence()
    for i, btn in drill_buttons.items():
        drill_running[i] = False
        btn.config(text=f"Perceuse {i + 1} : démarrer")
    messagebox.showwarning("Arrêt d'urgence", "Tous les systèmes sont arrêtés.")


def interrompre_routine():
    install.interrompre_routine()
    messagebox.showinfo("Info", "Routine interrompue.")


def on_close():
    install.arret_urgence()
    install.disconnect()
    root.destroy()


# ---------------- fenêtre ----------------
root = tk.Tk()
root.title("AQBTCM — routine 2026")
root.geometry("420x720")
root.configure(bg="#f4f4f4")
root.protocol("WM_DELETE_WINDOW", on_close)


def style_button(btn, font=FONT_NORMAL, bg="#ffffff", fg="#000000", border=1):
    btn.configure(
        font=font, bg=bg, fg=fg, relief="raised", bd=border, padx=10, pady=5,
        cursor="hand2", activebackground="#e6e6e6",
    )


# Arrêt d'urgence épinglé en bas, hors de la zone défilante : toujours
# accessible sans avoir à scroller.
btn_urgence = tk.Button(root, text="ARRÊT D'URGENCE", command=arret_urgence)
style_button(btn_urgence, font=FONT_BOLD, bg="#ff0000", fg="#ffffff", border=3)
btn_urgence.pack(side="bottom", fill="x", padx=20, pady=10)

# Zone défilante (canvas + scrollbar) qui contient tous les autres boutons.
canvas = tk.Canvas(root, bg="#f4f4f4", highlightthickness=0)
scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)

frame = tk.Frame(canvas, bg="#f4f4f4", padx=20, pady=15)
frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")
frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.bind("<Configure>", lambda e: canvas.itemconfigure(frame_id, width=e.width))


def on_mousewheel(event):
    # Linux : Button-4/5 ; Windows/macOS : <MouseWheel> avec event.delta
    if event.num == 4 or event.delta > 0:
        canvas.yview_scroll(-1, "units")
    elif event.num == 5 or event.delta < 0:
        canvas.yview_scroll(1, "units")


root.bind_all("<MouseWheel>", on_mousewheel)
root.bind_all("<Button-4>", on_mousewheel)
root.bind_all("<Button-5>", on_mousewheel)


def section(titre):
    tk.Label(frame, text=titre, font=FONT_BOLD, bg="#f4f4f4").pack(
        anchor="w", pady=(14, 4)
    )


# --- connexion ---
section("Connexion")
btn_connect = tk.Button(frame, text="Connecter ESP32 (LIGHTS + MOTORS)", command=connecter)
style_button(btn_connect)
btn_connect.pack(fill="x")

status_frame = tk.Frame(frame, bg="#f4f4f4")
status_frame.pack(fill="x", pady=(4, 0))
lbl_lights = tk.Label(status_frame, text="LIGHTS: ?", bg="#f4f4f4")
lbl_lights.pack(side="left", expand=True)
lbl_motors = tk.Label(status_frame, text="MOTORS: ?", bg="#f4f4f4")
lbl_motors.pack(side="right", expand=True)

# --- tests lumières ---
section("Lumières")
btn_test_ww = tk.Button(frame, text="Test WW (A → B → C)", command=lambda: run_action(install.test_ww_sequence))
style_button(btn_test_ww)
btn_test_ww.pack(fill="x", pady=(0, 6))

btn_test_cw = tk.Button(frame, text="Test CW (A → B → C)", command=lambda: run_action(install.test_cw_sequence))
style_button(btn_test_cw)
btn_test_cw.pack(fill="x", pady=(0, 6))

btn_phrases = tk.Button(
    frame, text="Envoyer phrases (morse, soliste B)",
    command=lambda: run_action(install.envoyer_phrases_origines, "B", "hesiode.txt"),
)
style_button(btn_phrases)
btn_phrases.pack(fill="x", pady=(0, 6))

btn_lights_off = tk.Button(frame, text="Éteindre toutes les lumières", command=install.all_lights_off)
style_button(btn_lights_off)
btn_lights_off.pack(fill="x")

# --- tests perceuses ---
section("Perceuses")
drill_buttons = {}
for i in range(3):
    b = tk.Button(frame, text=f"Perceuse {i + 1} : démarrer")
    b.configure(command=lambda i=i, b=b: toggle_drill(i, b))
    style_button(b)
    b.pack(fill="x", pady=(0, 4))
    drill_buttons[i] = b

btn_test_drills_seq = tk.Button(
    frame, text="Test séquentiel (1 → 2 → 3)",
    command=lambda: run_action(install.test_perceuses_sequentiel),
)
style_button(btn_test_drills_seq)
btn_test_drills_seq.pack(fill="x", pady=(4, 0))

# --- fumée ---
section("Fumée")
btn_smoke_pulse = tk.Button(
    frame, text="Impulsion unique",
    command=lambda: run_action(install.smoke_pulse, None, None, 1),
)
style_button(btn_smoke_pulse)
btn_smoke_pulse.pack(fill="x", pady=(0, 6))

btn_smoke_continu = tk.Button(
    frame, text="Démarrer pulsations continues",
    command=lambda: run_action(install.smoke_pulse, None, None, 0),
)
style_button(btn_smoke_continu)
btn_smoke_continu.pack(fill="x", pady=(0, 6))

btn_smoke_stop = tk.Button(frame, text="Arrêter la fumée", command=install.smoke_stop)
style_button(btn_smoke_stop)
btn_smoke_stop.pack(fill="x")

# --- musique / cœur ---
section("Musique & battement de cœur")
btn_music = tk.Button(frame, text="Test musique", command=lambda: run_action(install.music_start))
style_button(btn_music)
btn_music.pack(fill="x", pady=(0, 6))

btn_heart = tk.Button(
    frame, text="Test séquence battement de cœur",
    command=lambda: run_action(install.run_heartbeat_sequence),
)
style_button(btn_heart)
btn_heart.pack(fill="x")

# --- routine complète ---
section("Routine complète")
btn_routine = tk.Button(frame, text="Lancer la routine complète", command=install.routine_thread)
style_button(btn_routine, font=FONT_BOLD, bg="#ff9933", fg="#ffffff", border=2)
btn_routine.pack(fill="x", pady=(0, 6))

btn_interrompre = tk.Button(frame, text="Interrompre la routine", command=interrompre_routine)
style_button(btn_interrompre, font=FONT_BOLD, bg="#cc3333", fg="#ffffff", border=2)
btn_interrompre.pack(fill="x", pady=(0, 6))


if __name__ == "__main__":
    root.mainloop()
