import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import pygame
from pygame import mixer
import time
from time import sleep
import os
import threading

# ---------- VERROU POUR COMMUNICATION SERIE ----------
serial_lock = threading.Lock()

# ---------- LUMINAIRES & PERCEUSES ----------
luminaires = {
    "A": {"WW": {"A1": 2, "A2": 3, "A3": 4, "A4": 5}, "CW": {"A_COOL": 6}},
    "B": {"WW": {"B1": 7, "B2": 8, "B3": 9, "B4": 10}, "CW": {"B_COOL": 11}},
    "C": {"WW": {"C1": 12, "C2": 13, "C3": 44, "C4": 45}, "CW": {"C_COOL": 46}}
}
perceuses = {"DRILL_1": 3, "DRILL_2": 5, "DRILL_3": 6}

mega_light_1 = None
uno_drill = None

# ---------- COMMUNICATION ARDUINO ----------
def connecter_arduinos():
    global mega_light_1, uno_drill
    try:
        mega_light_1 = serial.Serial('COM6', 115200, timeout=1)
        print("Arduino MEGA LIGHTS connecté")
    except Exception as e:
        print(f"Erreur connexion Arduino MEGA LIGHTS : {e}")
    try:
        uno_drill = serial.Serial('COM10', 115200, timeout=1)
        print("Arduino UNO DRILL connecté")
    except Exception as e:
        print(f"Erreur connexion Arduino UNO DRILL : {e}")

def arduino_connexion():
    connecter_arduinos()
    messagebox.showinfo("Info", "Arduino connectés, voir console.")

# ---------- FONCTIONS PWM ----------
def set_pwm(pin, value):
    if mega_light_1 and mega_light_1.is_open:
        cmd = f"P{pin}:{value}\n"
        with serial_lock:
            try:
                mega_light_1.write(cmd.encode())
                time.sleep(0.01)  # anti-flood
                print(f"[MEGA] Envoyé: {cmd.strip()}")
            except serial.SerialTimeoutException:
                print(f"[Warning] Timeout série pour: {cmd.strip()}")
    else:
        print("Erreur : Arduino MEGA LIGHTS non connecté")

def set_pwm_uno(pin, value):
    if uno_drill and uno_drill.is_open:
        cmd = f"P{pin}:{value}\n"
        with serial_lock:
            try:
                uno_drill.write(cmd.encode())
                time.sleep(0.01)
                print(f"[UNO] Envoyé: {cmd.strip()}")
            except serial.SerialTimeoutException:
                print(f"[Warning] Timeout série UNO pour: {cmd.strip()}")
    else:
        print("Erreur : Arduino UNO DRILL non connecté")

# ---------- MUSIQUE ----------
def init_music():
    if not mixer.get_init():
        mixer.init()
        print("Mixer initialisé")

def music_start(filename="all_new_aqbtcm.mp3", volume=0.6):
    if not os.path.exists(filename):
        print(f"Fichier audio manquant: {filename}")
        return
    init_music()
    mixer.music.load(filename)
    mixer.music.set_volume(volume)
    mixer.music.play()
    print("Musique lancée")

def music_stop(fade_ms=3333):
    if mixer.get_init():
        mixer.music.fadeout(fade_ms)
        print("Musique stoppée")

def music_test():
    print("Test musique")
    sleep(1)
    music_start()
    sleep(6)
    music_stop()

# ---------- TESTS LUMINAIRES ----------
def test_ww_sequence():
    print("Test WW séquentiel (fade A->B->C)")
    for _ in range(2):
        for groupe in ["A", "B", "C"]:
            print(f"Test WW groupe {groupe}")
            pins = luminaires[groupe]["WW"].values()
            for lvl in range(0, 256, 32):
                for pin in pins:
                    set_pwm(pin, lvl)
                sleep(0.05)
            sleep(0.2)
            for lvl in reversed(range(0, 256, 32)):
                for pin in pins:
                    set_pwm(pin, lvl)
                sleep(0.05)
            sleep(0.1)
    print("Fin test WW")

def test_perceuses():
    print("Test perceuses (UNO)")
    for name, pin in perceuses.items():
        print(f"Test {name}")
        for lvl in range(0, 256, 32):
            set_pwm_uno(pin, lvl)
            sleep(0.05)
        sleep(0.3)
        for lvl in reversed(range(0, 256, 32)):
            set_pwm_uno(pin, lvl)
            sleep(0.05)
        sleep(0.4)
    print("Fin test perceuses")

# ---------- MORSE ET FADE SUR MOTS CLEFS ----------

# Table morse simplifiée (A-Z, 0-9)
MORSE_CODE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.', 'G': '--.',
    'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.',
    'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-', 'U': '..-',
    'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--', 'Z': '--..',
    '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....',
    '6': '-....', '7': '--...', '8': '---..', '9': '----.', '0': '-----'
}

DOT_DURATION = 0.2  # secondes
DASH_DURATION = DOT_DURATION * 3
SYMBOL_GAP = DOT_DURATION
LETTER_GAP = DOT_DURATION * 3
WORD_GAP = DOT_DURATION * 7

# Envoi d'une lettre en morse tube par tube (principal)
def send_letter_tube_by_tube(letter, tubes):
    code = MORSE_CODE.get(letter.upper(), '')
    if not code:
        print(f"Lettre '{letter}' inconnue en morse")
        return
    for symbol in code:
        level = 255 if symbol == '.' else 255  # Full ON for dot/dash
        duration = DOT_DURATION if symbol == '.' else DASH_DURATION
        # All tubes ON for duration
        for tube in tubes:
            set_pwm(tube, level)
        sleep(duration)
        # Off between symbols
        for tube in tubes:
            set_pwm(tube, 0)
        sleep(SYMBOL_GAP)
    sleep(LETTER_GAP - SYMBOL_GAP)

# Envoi avec fade progressif pour les groupes chœurs (fade mot important)
def send_letter_group_fade(letter, tubes):
    code = MORSE_CODE.get(letter.upper(), '')
    if not code:
        print(f"Lettre '{letter}' inconnue en morse (fade)")
        return
    for symbol in code:
        duration = DOT_DURATION if symbol == '.' else DASH_DURATION
        # fade in
        for lvl in range(0, 256, 64):
            for tube in tubes:
                set_pwm(tube, lvl)
            sleep(duration / 5)
        # fade out
        for lvl in reversed(range(0, 256, 64)):
            for tube in tubes:
                set_pwm(tube, lvl)
            sleep(duration / 5)
        sleep(SYMBOL_GAP)
    sleep(LETTER_GAP - SYMBOL_GAP)

# Thread de séquence morse (groupe principal)
def morse_sequence(main_tubes, choir1_tubes, choir2_tubes, phrase="HELLO", fade_word="HELLO"):
    print("Début séquence Morse")
    try:
        for letter in phrase:
            send_letter_tube_by_tube(letter, main_tubes)
            if letter in fade_word:
                send_letter_group_fade(letter, choir1_tubes)
                send_letter_group_fade(letter, choir2_tubes)
    except Exception as e:
        print(f"Erreur séquence Morse: {e}")
    print("Fin séquence Morse")

# Threads pour lancer la séquence
def start_morse_threads():
    # Exemple tubes : A est principal, B et C font fade
    main_tubes = list(luminaires["A"]["WW"].values())
    choir1_tubes = list(luminaires["B"]["WW"].values())
    choir2_tubes = list(luminaires["C"]["WW"].values())

    t = threading.Thread(target=morse_sequence, args=(main_tubes, choir1_tubes, choir2_tubes, "HELLO", "HELLO"))
    t.start()

# ---------- INTERFACE GRAPHIQUE ----------
root = tk.Tk()
root.title("Contrôle Arduino & Morse")

btn_connect = tk.Button(root, text="Connecter Arduino", command=arduino_connexion)
btn_connect.pack(padx=20, pady=10)

btn_music_test = tk.Button(root, text="Test Musique", command=music_test)
btn_music_test.pack(padx=20, pady=10)

btn_test_ww = tk.Button(root, text="Test WW séquentiel", command=test_ww_sequence)
btn_test_ww.pack(padx=20, pady=10)

btn_test_drills = tk.Button(root, text="Test Perceuses", command=test_perceuses)
btn_test_drills.pack(padx=20, pady=10)

btn_morse = tk.Button(root, text="Lancer séquence Morse", command=start_morse_threads)
btn_morse.pack(padx=20, pady=20)

root.mainloop()
