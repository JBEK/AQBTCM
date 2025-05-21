import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import pygame
from pygame import mixer
import time
from time import sleep
import os

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
    if mega_light_1 and mega_light_1.is_open:
        cmd = f"P{pin}:{value}\n"
        mega_light_1.write(cmd.encode())
        print(f"[MEGA] Envoyé: {cmd.strip()}")
    else:
        print("Erreur : Arduino MEGA LIGHTS non connecté")

def set_pwm_uno(pin, value):
    if uno_drill and uno_drill.is_open:
        cmd = f"P{pin}:{value}\n"
        uno_drill.write(cmd.encode())
        print(f"[UNO] Envoyé: {cmd.strip()}")
    else:
        print("Erreur : Arduino UNO DRILL non connecté")

# ---------------- TEST WW ------------------
def test_ww_sequence():
    print("Début du test des WW (séquentiel avec fade)")
    for _ in range(2):  # Deux cycles
        for groupe in ["A", "B", "C"]:
            print(f"→ Test WW groupe {groupe}")
            pins = luminaires[groupe]["WW"].values()
            for level in range(0, 256, 32):  # Fade-in
                for pin in pins:
                    set_pwm(pin, level)
                sleep(0.05)
            sleep(0.2)
            for level in reversed(range(0, 256, 32)):  # Fade-out
                for pin in pins:
                    set_pwm(pin, level)
                sleep(0.05)
            sleep(0.1)
    print("Fin du test WW")

# ---------------- TEST PERCEUSES ------------------
def test_perceuses():
    print("Test des perceuses (UNO)")
    for name, pin in perceuses.items():
        print(f"→ Test {name}")
        for level in range(0, 256, 32):  # Fade-in
            set_pwm_uno(pin, level)
            sleep(0.05)
        sleep(0.3)
        for level in reversed(range(0, 256, 32)):  # Fade-out
            set_pwm_uno(pin, level)
            sleep(0.05)
        sleep(0.4)
    print("Fin du test perceuses")

# ---------------- UI ------------------
root = tk.Tk()
root.title("Contrôle Arduino")

btn_lancer = tk.Button(root, text="Connection aux Arduino", command=arduino_connexion)
btn_lancer.pack(padx=20, pady=20)

btn_test_music = tk.Button(root, text="Test Music", command=music_test)
btn_test_music.pack(padx=20, pady=(5, 20))

btn_test_ww = tk.Button(root, text="Test WW (A → B → C)", command=test_ww_sequence)
btn_test_ww.pack(padx=20, pady=(5, 20))

btn_test_drills = tk.Button(root, text="Test Perceuses", command=test_perceuses)
btn_test_drills.pack(padx=20, pady=(5, 20))

root.mainloop()
