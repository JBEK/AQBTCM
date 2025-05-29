import tkinter as tk
from tkinter import messagebox
import serial
import pygame
from pygame import mixer
import time
from time import sleep
import os
import re
import threading

stop_flag = threading.Event()

# ---------------- LUMINAIRES ------------------
luminaires = {
    "A": {
        "WW": {"A1": 2, "A2": 3, "A3": 4, "A4": 5},
        "CW": {"A_COOL": 6}
    },
    "B": {
        "WW": {"B1": 7, "B2": 8, "B3": 9, "B4": 10},
        "CW": {"B_COOL": 11}
    },
    "C": {
        "WW": {"C1": 12, "C2": 13, "C3": 44, "C4": 45},
        "CW": {"C_COOL": 46}
    }
}

# ---------------- PERCEUSES (UNO) ------------------
perceuses = {
    "DRILL_1": 3,
    "DRILL_2": 5,
    "DRILL_3": 6
}
relai_fumee = 8  # par exemple, change si nécessaire

# ---------------- VARIABLES GLOBALES ------------------
mega_light_1 = None
uno_drill = None

# ---------------- MUSIQUE ------------------
def init_music():
    if not mixer.get_init():
        mixer.init()
        print("Mixer initialized")

def music_start(filename="all_new_aqbtcm.mp3", volume=0.6):
    if not os.path.exists(filename):
        print(f"Audio file not found: {filename}")
        return
    init_music()
    mixer.music.load(filename)
    mixer.music.set_volume(volume)
    mixer.music.play()
    print("Starting music")

def music_stop(fade_ms=3333):
    if mixer.get_init():
        mixer.music.fadeout(fade_ms)
        print("Music stopped")

def music_test():
    print("Testing music")
    sleep(1)
    music_start()
    sleep(6)
    music_stop()

# ---------------- COMMUNICATION ARDUINO ------------------
def connecter_arduinos():
    global mega_light_1, uno_drill
    try:
        mega_light_1 = serial.Serial('COM6', 115200, timeout=1)
        print("Arduino MEGA LIGHTS connected")
    except Exception as e:
        print(f"Failed to connect to Arduino MEGA LIGHTS: {e}")
    
    try:
        uno_drill = serial.Serial('COM10', 115200, timeout=1)
        print("Arduino UNO DRILL connected")
    except Exception as e:
        print(f"Failed to connect to Arduino UNO DRILL: {e}")

def arduino_connexion():
    connecter_arduinos()
    messagebox.showinfo("Info", "Arduino connectés, voir console.")

# ---------------- PWM UTILS ------------------
def set_pwm(pin, value):
    global mega_light_1
    if mega_light_1 and mega_light_1.is_open:
        cmd = f"P{pin}:{value}\n"
        mega_light_1.write(cmd.encode())
        print(f"[MEGA] Envoyé: {cmd.strip()}")
    else:
        print("Erreur : Arduino MEGA LIGHTS non connecté")

def set_pwm_uno(pin, value):
    global uno_drill
    if uno_drill and uno_drill.is_open:
        cmd = f"P{pin}:{value}\n"
        uno_drill.write(cmd.encode())
        print(f"[UNO] Envoyé: {cmd.strip()}")
    else:
        print("Erreur : Arduino UNO DRILL non connecté")

# ---------------- LIGHTS ------------------
def test_ww_sequence():
    print("Début du test des WW (séquentiel avec fade)")
    for _ in range(2):  # Deux cycles
        for groupe in ["A", "B", "C"]:
            if stop_flag.is_set():
                print("Test WW interrompu")
                return
            print(f"→ Test WW groupe {groupe}")
            pins = luminaires[groupe]["WW"].values()
            for level in range(0, 256, 32):  # Fade-in
                if stop_flag.is_set():
                    print("Test WW interrompu")
                    return
                for pin in pins:
                    set_pwm(pin, level)
                sleep(0.05)
            sleep(0.2)
            for level in reversed(range(0, 256, 32)):  # Fade-out
                if stop_flag.is_set():
                    print("Test WW interrompu")
                    return
                for pin in pins:
                    set_pwm(pin, level)
                sleep(0.05)
            sleep(0.1)
    print("Fin du test WW")

# ---------------- DRILLS ------------------
def test_perceuses():
    print("Test des perceuses (UNO)")
    for name, pin in perceuses.items():
        if stop_flag.is_set():
            print("Test perceuses interrompu")
            return
        print(f"→ Test {name}")
        for level in range(0, 256, 32):  # Fade-in
            if stop_flag.is_set():
                print("Test perceuses interrompu")
                return
            set_pwm_uno(pin, level)
            sleep(0.05)
        sleep(0.3)
        for level in reversed(range(0, 256, 32)):  # Fade-out
            if stop_flag.is_set():
                print("Test perceuses interrompu")
                return
            set_pwm_uno(pin, level)
            sleep(0.05)
        sleep(0.4)
    print("Fin du test perceuses")

def all_drills_on(vitesse=200):
    for pin in [3, 5, 6]:
        set_pwm_uno(pin, vitesse)

def all_drills_on_thread(vitesse=200):
    threading.Thread(target=all_drills_on, args=(vitesse,), daemon=True).start()

# ---------------- SMOKE ------------------

def smoke_on():
    print("Allumage machine à fumée (UNO - Digital Relay)")
    if uno_drill and uno_drill.is_open:
        uno_drill.write(b"FUM_ON\n")
        print("[UNO] FUM_ON envoyé")
        sleep(3)
        uno_drill.write(b"FUM_OFF\n")
        print("[UNO] FUM_OFF envoyé")
    else:
        print("Arduino UNO DRILL non connecté")



# ---------------- ENVOI DES PHRASES ORIGINES ------------------
def attendre_ok():
    global mega_light_1
    if not mega_light_1 or not mega_light_1.is_open:
        return False
    start = time.time()
    timeout = 145  # secondes max d'attente
    buffer = ""
    while time.time() - start < timeout:
        if stop_flag.is_set():
            print("Attente OK interrompue")
            return False
        if mega_light_1.in_waiting > 0:
            buffer += mega_light_1.read(mega_light_1.in_waiting).decode('utf-8')
            if "OK" in buffer:
                return True
        time.sleep(0.05)
    print("Timeout attente OK de l'Arduino")
    return False

def envoyer_phrases_origines(soliste="A", fichier="test.txt"):
    global mega_light_1
    if not mega_light_1 or not mega_light_1.is_open:
        print("Arduino MEGA LIGHTS non connecté, impossible d'envoyer les phrases.")
        return
    
    if not os.path.exists(fichier):
        print(f"Fichier {fichier} introuvable.")
        return
    
    with open(fichier, 'r', encoding='utf-8') as f:
        texte = f.read()
    
    phrases = [p.strip() for p in re.split(r'\.\s*', texte) if p.strip()]
    print(f"{len(phrases)} phrases extraites du fichier.")
    
    for phrase in phrases:
        if stop_flag.is_set():
            print("Envoi phrases interrompu")
            return
        match = re.search(r'\*(.+?)\*', phrase)
        if match:
            mot_choeur = match.group(1)
            phrase_nettoyee = phrase.replace(f"*{mot_choeur}*", mot_choeur)
        else:
            mot_choeur = ""
            phrase_nettoyee = phrase
        
        cmd = f"M:{soliste}|{phrase_nettoyee}|*{mot_choeur}*\n"
        mega_light_1.write(cmd.encode('utf-8'))
        print(f"Envoyé à MEGA: {cmd.strip()}")
        
        if not attendre_ok():
            print("Erreur : pas de réponse OK de l'Arduino, arrêt de l'envoi.")
            break

    print("Fin de l'envoi des phrases.")

# ---------------- ROUTINE ------------------
def routine():
    stop_flag.clear()
    print("Routine lancée.")
    smoke_on()
    music_start(filename="all_new_aqbtcm.mp3", volume=0.8)
    sleep(3)

    # Lancer les séquences en parallèle
    t1 = threading.Thread(target=test_ww_sequence)
    t2 = threading.Thread(target=test_perceuses)
    t1.start()
    t2.start()

    # Ensuite tu continues ta propre boucle de routine
    for i in range(20):
        if stop_flag.is_set():
            print("Routine interrompue par l'utilisateur.")
            break
        print(f"Étape {i+1}/20")
        sleep(1)

    music_stop()
    print("Fin de routine.")

def lancer_routine_thread():
    threading.Thread(target=routine, daemon=True).start()

def interrompre_routine():
    stop_flag.set()  # Déclenche l'arrêt
    music_stop()
    print("Signal d'interruption envoyé.")
    messagebox.showinfo("Info", "Routine interrompue.")

def arret_urgence():
    print("⚠️ ARRÊT D'URGENCE INITIÉ ⚠️")
    stop_flag.set()

    # Stop musique immédiatement
    if mixer.get_init():
        mixer.music.stop()
        print("⏹ Musique arrêtée brutalement")

    # Couper la fumée
    if uno_drill and uno_drill.is_open:
        try:
            uno_drill.write(b"FUM_OFF\n")
            print("💨 Fumée désactivée")
        except Exception as e:
            print(f"Erreur arrêt fumée : {e}")

    # Éteindre toutes les lumières
    for groupe in luminaires.values():
        for sous_groupe in groupe.values():
            for pin in sous_groupe.values():
                try:
                    set_pwm(pin, 0)
                except Exception as e:
                    print(f"Erreur arrêt lumière pin {pin} : {e}")

    # Éteindre toutes les perceuses
    for pin in perceuses.values():
        try:
            set_pwm_uno(pin, 0)
        except Exception as e:
            print(f"Erreur arrêt perceuse pin {pin} : {e}")

    print("🚨 Tous les systèmes ont été mis hors tension.")
    messagebox.showwarning("Arrêt d'urgence", "Tous les systèmes sont arrêtés brutalement.")


# ---------------- UI HELVETICA ÉPURÉ ------------------
root = tk.Tk()
root.title("Contrôle Arduino")
root.geometry("400x500")
root.configure(bg="#f4f4f4")  # Fond clair

# Polices Helvetica
FONT_NORMAL = ("HelveticaNeueLT Pro 65 Md", 10)
FONT_BOLD = ("HelveticaNeueLT Pro 95 BlkCn", 10, "bold")

# Cadre principal
frame = tk.Frame(root, bg="#f4f4f4")
frame.pack(expand=True, fill="both", padx=20, pady=20)

def style_button(btn, font=FONT_NORMAL, bg="#ffffff", fg="#000000", border=1):
    btn.configure(font=font, bg=bg, fg=fg, relief="raised", bd=border, padx=10, pady=5,
                  cursor="hand2", activebackground="#e6e6e6")

btn_lancer = tk.Button(frame, text="Connexion aux Arduino", command=arduino_connexion)
style_button(btn_lancer)
btn_lancer.pack(fill="x", pady=(0, 10))

btn_test_music = tk.Button(frame, text="Test Musique", command=music_test)
style_button(btn_test_music)
btn_test_music.pack(fill="x", pady=(0, 10))

btn_test_ww = tk.Button(frame, text="Test WW (A → B → C)", command=test_ww_sequence)
style_button(btn_test_ww)
btn_test_ww.pack(fill="x", pady=(0, 10))

btn_test_drills = tk.Button(frame, text="Test Perceuses", command=test_perceuses)
style_button(btn_test_drills)
btn_test_drills.pack(fill="x", pady=(0, 10))

btn_all_on = tk.Button(frame, text="Allumer toutes les perceuses", command=lambda: all_drills_on_thread(200))
style_button(btn_all_on)
btn_all_on.pack(fill="x", pady=(0, 10))

btn_test_fumee = tk.Button(frame, text="Test Fumée", command=smoke_on)
style_button(btn_test_fumee)
btn_test_fumee.pack(fill="x", pady=(0, 10))

btn_envoyer_phrases = tk.Button(frame, text="Envoyer Phrases", command=envoyer_phrases_origines)
style_button(btn_envoyer_phrases)
btn_envoyer_phrases.pack(fill="x", pady=(0, 10))

btn_lancer_routine = tk.Button(frame, text="Lancer la routine", command=lancer_routine_thread)
style_button(btn_lancer_routine, font=FONT_BOLD, bg="#ff9933", fg="#ffffff", border=2)
btn_lancer_routine.pack(fill="x", pady=(20, 10))

btn_interrompre_routine = tk.Button(frame, text="Interrompre la routine", command=interrompre_routine)
style_button(btn_interrompre_routine, font=FONT_BOLD, bg="#cc3333", fg="#ffffff", border=2)
btn_interrompre_routine.pack(fill="x", pady=(0, 10))

btn_arret_urgence = tk.Button(frame, text="ARRÊT D'URGENCE", command=arret_urgence)
style_button(btn_arret_urgence, font=FONT_BOLD, bg="#ff0000", fg="#ffffff", border=3)
btn_arret_urgence.pack(fill="x", pady=(20, 10))

root.mainloop()
