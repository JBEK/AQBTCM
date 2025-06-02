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
# stop_event_battement = threading.Event() # Remplacé par stop_flag pour heart_play


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

def music_test_interruptible():
    # stop_flag.clear() est géré par run_test_in_thread ou la fonction appelante
    print("Testing music")
    if stop_flag.is_set(): print("Music test (pre-start) interrupted."); return

    music_start()
    
    start_time = time.time()
    duration = 6 # Durée du test musical
    interrupted = False
    while time.time() - start_time < duration:
        if stop_flag.is_set():
            print("Music test interrupted during playback.")
            interrupted = True
            break
        sleep(0.1) # Vérifier toutes les 100ms
    
    music_stop() # Toujours arrêter la musique
    if not interrupted:
        print("Music test finished normally.")
    else:
        # Le message d'interruption a déjà été affiché
        pass

# ---------------- COMMUNICATION ARDUINO ------------------
def connecter_arduinos():
    global mega_light_1, uno_drill
    try:
        # Ajout d'un write_timeout et attente/vidage buffer
        mega_light_1 = serial.Serial('COM6', 115200, timeout=1, write_timeout=1)
        print("Arduino MEGA LIGHTS connected")
        time.sleep(2) # Laisser le temps à l'Arduino de s'initialiser
        if mega_light_1.in_waiting > 0:
            mega_light_1.read(mega_light_1.in_waiting)
            print("Initial input buffer from MEGA cleared.")

    except Exception as e:
        print(f"Failed to connect to Arduino MEGA LIGHTS: {e}")
        mega_light_1 = None # S'assurer qu'il est None en cas d'échec
    
    try:
        # Ajout d'un write_timeout et attente/vidage buffer
        uno_drill = serial.Serial('COM10', 115200, timeout=1, write_timeout=1)
        print("Arduino UNO DRILL connected")
        time.sleep(2) # Laisser le temps à l'Arduino de s'initialiser
        if uno_drill.in_waiting > 0:
            uno_drill.read(uno_drill.in_waiting)
            print("Initial input buffer from UNO cleared.")

    except Exception as e:
        print(f"Failed to connect to Arduino UNO DRILL: {e}")
        uno_drill = None # S'assurer qu'il est None en cas d'échec

def arduino_connexion():
    connecter_arduinos()
    messagebox.showinfo("Info", "Tentative de connexion aux Arduinos. Vérifiez la console pour les détails.")

# ---------------- PWM UTILS ------------------
def set_pwm(pin, value):
    global mega_light_1
    if mega_light_1 and mega_light_1.is_open:
        cmd = f"P{pin}:{value}\n"
        try:
            mega_light_1.write(cmd.encode())
            print(f"[MEGA] Envoyé: {cmd.strip()}")
            # Attendre une réponse "OK" ou "ERR"
            # response = mega_light_1.readline().decode().strip()
            # print(f"[MEGA] Reçu: {response}")
        except Exception as e:
            print(f"Erreur envoi PWM à MEGA: {e}")
    else:
        print("Erreur : Arduino MEGA LIGHTS non connecté pour set_pwm")

def set_pwm_uno(pin, value):
    global uno_drill
    if uno_drill and uno_drill.is_open:
        cmd = f"P{pin}:{value}\n"
        try:
            uno_drill.write(cmd.encode())
            print(f"[UNO] Envoyé: {cmd.strip()}")
            # response = uno_drill.readline().decode().strip()
            # print(f"[UNO] Reçu: {response}")
        except Exception as e:
            print(f"Erreur envoi PWM à UNO: {e}")
    else:
        print("Erreur : Arduino UNO DRILL non connecté pour set_pwm_uno")

# ---------------- LIGHTS ------------------
def test_ww_sequence():
    print("Début du test des WW (séquentiel avec fade)")
    for _ in range(2):  # Deux cycles
        for groupe_nom in ["A", "B", "C"]:
            if stop_flag.is_set():
                print("Test WW interrompu")
                return
            print(f"→ Test WW groupe {groupe_nom}")
            pins_ww = luminaires[groupe_nom]["WW"].values()
            
            # Fade-in
            for level in range(0, 256, 32):
                if stop_flag.is_set(): print("Test WW interrompu"); return
                for pin in pins_ww:
                    set_pwm(pin, level)
                sleep(0.05)
            sleep(0.2)
            
            # Fade-out
            for level in reversed(range(0, 256, 32)):
                if stop_flag.is_set(): print("Test WW interrompu"); return
                for pin in pins_ww:
                    set_pwm(pin, level)
                sleep(0.05)
            sleep(0.1) # Petite pause entre les groupes
    print("Fin du test WW")

# ---------------- DRILLS ------------------
def test_perceuses():
    print("Test des perceuses (UNO)")
    for name, pin in perceuses.items():
        if stop_flag.is_set():
            print("Test perceuses interrompu")
            return
        print(f"→ Test {name} (pin {pin})")
        # Fade-in
        for level in range(0, 256, 32):
            if stop_flag.is_set(): print("Test perceuses interrompu"); return
            set_pwm_uno(pin, level)
            sleep(0.05)
        sleep(0.3)
        # Fade-out
        for level in reversed(range(0, 256, 32)):
            if stop_flag.is_set(): print("Test perceuses interrompu"); return
            set_pwm_uno(pin, level)
            sleep(0.05)
        sleep(0.4) # Pause entre les perceuses
    print("Fin du test perceuses")

def all_drills_on(vitesse=200):
    print(f"Allumage de toutes les perceuses à la vitesse {vitesse}")
    for pin in perceuses.values():
        if stop_flag.is_set(): print("All_drills_on interrompu"); return
        set_pwm_uno(pin, vitesse)

def all_drills_on_thread(vitesse=200):
    # Enveloppe pour gérer stop_flag.clear()
    def target_with_clear():
        stop_flag.clear()
        all_drills_on(vitesse)
    threading.Thread(target=target_with_clear, daemon=True).start()
    
# ---------------- SMOKE ------------------
def smoke_out(duration=5): # Durée par défaut de 5 secondes pour un test
    global uno_drill, stop_flag
    print(f"Activation machine à fumée (UNO) pour {duration} secondes.")
    if uno_drill and uno_drill.is_open:
        try:
            uno_drill.write(b"FUM_ON\n")
            print("[UNO] Commande FUM_ON envoyée")

            # Attendre la durée spécifiée, en vérifiant stop_flag
            start_time = time.time()
            while time.time() - start_time < duration:
                if stop_flag.is_set():
                    print("Activation fumée interrompue par stop_flag.")
                    break # Sortir de la boucle d'attente
                sleep(0.1) # Vérifier le flag toutes les 100ms
            
            # Toujours envoyer FUM_OFF, même si interrompu, pour s'assurer que la fumée s'arrête
            uno_drill.write(b"FUM_OFF\n")
            print("[UNO] Commande FUM_OFF envoyée")

        except Exception as e:
            print(f"Erreur envoi commande fumée: {e}")
            # Essayer d'envoyer FUM_OFF en cas d'erreur pendant FUM_ON ou l'attente
            if uno_drill and uno_drill.is_open:
                try: uno_drill.write(b"FUM_OFF\n"); print("[UNO] Commande FUM_OFF envoyée (après erreur)")
                except: pass
    else:
        print("Arduino UNO DRILL non connecté pour smoke_out")

def smoke_out_thread(duration=5):
    # Enveloppe pour gérer stop_flag.clear()
    def target_with_clear():
        stop_flag.clear()
        smoke_out(duration)
    thread = threading.Thread(target=target_with_clear, daemon=True)
    thread.start()
# ---------------- ENVOI DES PHRASES ORIGINES (Morse) ------------------
def attendre_ok(timeout_seconds=145): # Augmentation du timeout par défaut
    global mega_light_1
    if not mega_light_1 or not mega_light_1.is_open:
        print("MEGA non connecté, impossible d'attendre OK.")
        return False
    
    print("Attente du OK de l'Arduino MEGA...")
    start_time = time.time()
    buffer = ""
    while time.time() - start_time < timeout_seconds:
        if stop_flag.is_set():
            print("Attente OK interrompue par stop_flag.")
            return False
        try:
            if mega_light_1.in_waiting > 0:
                bytes_to_read = mega_light_1.in_waiting
                buffer += mega_light_1.read(bytes_to_read).decode('utf-8', errors='replace')
                if "OK" in buffer:
                    print("OK reçu de l'Arduino MEGA.")
                    return True
                # Gérer les messages d'erreur potentiels de l'Arduino
                if "ERR" in buffer:
                    print(f"Erreur reçue de l'Arduino MEGA: {buffer.strip()}")
                    return False # Ou gérer l'erreur différemment
        except Exception as e:
            print(f"Erreur durant l'attente du OK: {e}")
            return False
        time.sleep(0.05) # Ne pas surcharger le CPU
    print(f"Timeout ({timeout_seconds}s) : OK non reçu de l'Arduino MEGA.")
    return False

def envoyer_phrases_origines(soliste="A", fichier="hesiode.txt"):
    global mega_light_1
    if not mega_light_1 or not mega_light_1.is_open:
        print("Arduino MEGA LIGHTS non connecté, impossible d'envoyer les phrases.")
        return
    
    if not os.path.exists(fichier):
        print(f"Fichier de phrases '{fichier}' introuvable.")
        return
    
    try:
        with open(fichier, 'r', encoding='utf-8') as f:
            texte = f.read()
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier {fichier}: {e}")
        return
    
    phrases = [p.strip() for p in re.split(r'\.\s*', texte) if p.strip()]
    if not phrases:
        print(f"Aucune phrase valide trouvée dans {fichier}.")
        return
        
    print(f"{len(phrases)} phrases extraites du fichier '{fichier}'.")
    
    for i, phrase in enumerate(phrases):
        if stop_flag.is_set():
            print("Envoi des phrases interrompu par stop_flag.")
            return
            
        match = re.search(r'\*(.+?)\*', phrase)
        if match:
            mot_choeur = match.group(1)
            phrase_nettoyee = phrase.replace(f"*{mot_choeur}*", mot_choeur).strip()
        else:
            mot_choeur = "" # Envoyer une chaîne vide si pas de mot pour le chœur
            phrase_nettoyee = phrase.strip()
        
        # S'assurer que la phrase n'est pas vide après nettoyage
        if not phrase_nettoyee and not mot_choeur:
            print(f"Phrase {i+1} vide, ignorée.")
            continue

        cmd = f"M:{soliste}|{phrase_nettoyee}|*{mot_choeur}*\n"
        
        try:
            mega_light_1.write(cmd.encode('utf-8'))
            print(f"Envoyé à MEGA: {cmd.strip()}")
        except Exception as e:
            print(f"Erreur lors de l'envoi de la commande Morse à MEGA: {e}")
            # Peut-être tenter de se reconnecter ou arrêter
            return 
        
        if not attendre_ok(): # Utilise le timeout par défaut de attendre_ok
            print("Erreur critique : pas de réponse OK de l'Arduino après l'envoi d'une phrase. Arrêt de l'envoi.")
            # Ici, vous pourriez vouloir arrêter toute la routine ou tenter une récupération
            return # Arrête d'envoyer d'autres phrases

    print("Fin de l'envoi de toutes les phrases.")

# ---------------- HEART ------------------
def heart_play(duration=10):
    global mega_light_1, stop_flag 
    if not mega_light_1 or not mega_light_1.is_open:
        print("Arduino MEGA LIGHTS non connecté, impossible d'envoyer les battements.")
        return

    start_time = time.time()
    try:
        with open("heart.txt", "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("Fichier heart.txt introuvable.")
        return
    
    if not lines:
        print("Fichier heart.txt est vide.")
        return

    idx = 0
    n = len(lines)
    consecutive_errors = 0
    max_consecutive_errors = 5 # Arrêter après 5 erreurs d'écriture consécutives

    print("Démarrage Heartbeat...")
    while time.time() - start_time < duration:
        if stop_flag.is_set(): 
            print("Heartbeat interrompu par stop_flag.")
            break

        value_str = lines[idx].strip()
        if value_str.isdigit():
            value = int(value_str)
            value = max(0, min(255, value)) # S'assurer que la valeur est dans la plage PWM
            
            cmd = f"H:{value}\n"
            try:
                bytes_written = mega_light_1.write(cmd.encode())
                # print(f"[MEGA] Heartbeat: {cmd.strip()} ({bytes_written} bytes)") # Débogage
                mega_light_1.flush() # Essayer de forcer l'envoi des données
                consecutive_errors = 0 # Réinitialiser le compteur d'erreurs en cas de succès
            except serial.SerialTimeoutException:
                print(f"Timeout lors de l'envoi Heartbeat: {cmd.strip()}. L'Arduino ne suit peut-être pas.")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    print("Trop d'erreurs d'écriture consécutives. Arrêt de Heartbeat.")
                    break
            except Exception as e:
                print(f"Erreur envoi Heartbeat: {e} pour la commande {cmd.strip()}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    print("Trop d'erreurs d'écriture consécutives. Arrêt de Heartbeat.")
                    break
            
            time.sleep(0.02)  # Rythme d'envoi (environ 50Hz)
        else:
            print(f"Valeur non numérique ignorée dans heart.txt: {value_str}")

        idx = (idx + 1) % n # Boucle sur le fichier
    
    # Optionnel: éteindre les LEDs à la fin de la séquence heartbeat
    # Si une autre commande suit, resetAllModes() sur l'Arduino s'en chargera.
    # if mega_light_1 and mega_light_1.is_open:
    #    try:
    #        mega_light_1.write(b"H:0\n") 
    #    except Exception as e:
    #        print(f"Erreur envoi H:0 à la fin de Heartbeat: {e}")
    print("Fin Heartbeat.")

# ---------------- ROUTINE ------------------
def routine():
    stop_flag.clear()
    print("Routine lancée.")
    
    # Initialisation des éléments
    music_start(filename="all_new_aqbtcm.mp3", volume=0.8)
    smoke_out_thread(duration=10) # Activation de la fumée pour 10 secondes (non bloquant)
    sleep(1) # Petite pause pour que la musique et la fumée démarrent

    # Création des threads pour les séquences parallèles
    # Note: les fonctions cibles (test_ww_sequence, etc.) doivent vérifier stop_flag
    thread_ww = threading.Thread(target=test_ww_sequence)
    thread_drills = threading.Thread(target=test_perceuses)
    thread_heart = threading.Thread(target=heart_play, args=(15,)) # Heartbeat pendant 25 secondes
    thread_phrases = threading.Thread(target=envoyer_phrases_origines, args=("B", "test.txt")) # Soliste B

    # Démarrage des threads
    print("Démarrage thread WW...")
    thread_ww.start()
    sleep(5) # Décalage pour le démarrage des perceuses

    print("Démarrage thread Perceuses...")
    thread_drills.start()
    sleep(10) # Décalage pour le démarrage du heartbeat

    print("Démarrage thread Heartbeat...")
    thread_heart.start()
    sleep(15) # Décalage pour le démarrage de l'envoi des phrases

    print("Démarrage thread Phrases Morse...")
    thread_phrases.start()

    # Attendre la fin des threads principaux avant de continuer ou de terminer la routine
    # Cela assure que la routine ne se termine pas prématurément
    thread_ww.join()
    print("Thread WW terminé.")
    thread_drills.join()
    print("Thread Perceuses terminé.")
    thread_heart.join()
    print("Thread Heartbeat terminé.")
    thread_phrases.join()
    print("Thread Phrases Morse terminé.")

    # Boucle de "maintenance" ou d'attente si d'autres actions sont prévues plus tard
    # Ou simplement pour garder la routine active jusqu'à une interruption manuelle
    # Par exemple, attendre 30 secondes de plus avant d'arrêter la musique
    wait_end_time = time.time()
    while time.time() - wait_end_time < 30:
        if stop_flag.is_set():
            print("Routine interrompue pendant l'attente finale.")
            break
        sleep(1)
        print("Routine en attente finale...")

    music_stop()
    print("Fin de routine.")

def lancer_routine_thread():
    # S'assurer qu'une seule routine est lancée à la fois si nécessaire
    # Pour l'instant, on permet de lancer plusieurs fois, mais attention aux conflits sur les Arduinos
    routine_thread = threading.Thread(target=routine, daemon=True)
    routine_thread.start()

def interrompre_routine():
    print("Signal d'interruption envoyé à la routine et aux séquences.")
    stop_flag.set()  # Déclenche l'arrêt pour toutes les fonctions qui vérifient ce flag
    music_stop()     # Arrêter la musique

    print("Envoi des commandes d'arrêt aux Arduinos...")

    # Couper la fumée (UNO)
    if uno_drill and uno_drill.is_open:
        try:
            uno_drill.write(b"FUM_OFF\n")
            print("💨 Commande FUM_OFF envoyée à l'UNO.")
        except Exception as e:
            print(f"Erreur lors de l'envoi de FUM_OFF à l'UNO : {e}")

    # Éteindre toutes les lumières (MEGA)
    # Envoyer H:0 pour éteindre tous les WW (gérés par Morse ou Heartbeat)
    if mega_light_1 and mega_light_1.is_open:
        try:
            mega_light_1.write(b"H:0\n") 
            print("💡 Commande H:0 envoyée à MEGA pour éteindre les WW.")
        except Exception as e:
            print(f"Erreur lors de l'envoi de H:0 à MEGA : {e}")
        # Éteindre les CW individuellement
        for groupe_nom in luminaires:
            for pin_cw in luminaires[groupe_nom]["CW"].values():
                set_pwm(pin_cw, 0) # Utilise la fonction set_pwm qui envoie P:pin:0
    
    # Éteindre toutes les perceuses (UNO)
    for pin_perceuse in perceuses.values():
        set_pwm_uno(pin_perceuse, 0) # Utilise la fonction set_pwm_uno

    print("Commandes d'arrêt envoyées.")
    messagebox.showinfo("Info", "Routine interrompue.")

def arret_urgence():
    print("⚠️ ARRÊT D'URGENCE INITIÉ ⚠️")
    stop_flag.set() # Stopper toutes les boucles et threads Python

    # Stop musique immédiatement
    if mixer.get_init():
        mixer.music.stop()
        print("⏹ Musique arrêtée brutalement")

    # Couper la fumée (commande explicite à l'Arduino UNO)
    if uno_drill and uno_drill.is_open:
        try:
            uno_drill.write(b"FUM_OFF\n") # Assurez-vous que l'UNO gère FUM_OFF
            print("💨 Commande FUM_OFF envoyée à l'UNO.")
        except Exception as e:
            print(f"Erreur lors de l'envoi de FUM_OFF à l'UNO : {e}")

    # Éteindre toutes les lumières (commandes explicites à l'Arduino MEGA)
    # Envoyer H:0 pour éteindre tous les WW gérés par le mode Heartbeat/Morse
    if mega_light_1 and mega_light_1.is_open:
        try:
            mega_light_1.write(b"H:0\n") 
            print("💡 Commande H:0 envoyée à MEGA pour éteindre les WW.")
        except Exception as e:
            print(f"Erreur lors de l'envoi de H:0 à MEGA : {e}")
        # Éteindre les CW individuellement si nécessaire (si P: ne les a pas déjà éteints)
        for groupe_nom in luminaires:
            for pin_cw in luminaires[groupe_nom]["CW"].values():
                try:
                    set_pwm(pin_cw, 0) # Utilise la fonction set_pwm qui envoie P:pin:0
                except Exception as e:
                    print(f"Erreur arrêt lumière CW pin {pin_cw} : {e}")
    
    # Éteindre toutes les perceuses (commandes explicites à l'Arduino UNO)
    for pin_perceuse in perceuses.values():
        try:
            set_pwm_uno(pin_perceuse, 0) # Utilise la fonction set_pwm_uno
        except Exception as e:
            print(f"Erreur arrêt perceuse pin {pin_perceuse} : {e}")

    print("🚨 Tentative d'arrêt de tous les systèmes.")
    messagebox.showwarning("Arrêt d'urgence", "Tous les systèmes ont reçu un ordre d'arrêt.")

# ---------- LANCEUR DE TEST EN THREAD ----------
def run_test_in_thread(target_function, *args):
    """Lance une fonction de test dans un thread dédié, en s'assurant que stop_flag est clear."""
    def wrapper():
        stop_flag.clear()
        target_function(*args)
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()

# ---------------- UI HELVETICA ÉPURÉ ------------------
root = tk.Tk()
root.title("Contrôle Installation AQBTCM")
root.geometry("450x550") # Un peu plus grand pour les boutons
root.configure(bg="#f0f0f0")

# Polices (vérifiez si elles sont installées sur votre système)
# Vous pouvez utiliser des polices standard comme "Arial" ou "Calibri" si Helvetica n'est pas dispo
try:
    FONT_NORMAL = ("HelveticaNeueLT Pro 65 Md", 10)
    FONT_BOLD = ("HelveticaNeueLT Pro 95 BlkCn", 10, "bold")
except tk.TclError:
    print("Polices Helvetica non trouvées, utilisation de polices par défaut.")
    FONT_NORMAL = ("Arial", 10)
    FONT_BOLD = ("Arial", 10, "bold")


# Cadre principal
frame = tk.Frame(root, bg="#f0f0f0")
frame.pack(expand=True, fill="both", padx=20, pady=20)

def style_button(btn, font=FONT_NORMAL, bg_color="#ffffff", fg_color="#333333", active_bg="#e0e0e0", active_fg="#000000", bd_width=1):
    btn.configure(
        font=font, 
        bg=bg_color, 
        fg=fg_color, 
        relief="raised", 
        bd=bd_width, 
        padx=10, pady=6,
        cursor="hand2", 
        activebackground=active_bg,
        activeforeground=active_fg,
        highlightthickness=2,
        highlightbackground = "#d0d0d0" # Couleur de la bordure quand pas focus
    )
    btn.bind("<Enter>", lambda e: btn.configure(bg=active_bg))
    btn.bind("<Leave>", lambda e: btn.configure(bg=bg_color))


btn_connecter = tk.Button(frame, text="Connexion aux Arduinos", command=arduino_connexion)
style_button(btn_connecter, bg_color="#e7f0ff", fg_color="#0052cc")
btn_connecter.pack(fill="x", pady=(0, 10))

btn_test_music = tk.Button(frame, text="Test Musique", command=lambda: run_test_in_thread(music_test_interruptible))
style_button(btn_test_music)
btn_test_music.pack(fill="x", pady=(0, 5))

btn_test_ww = tk.Button(frame, text="Test Lumières WW (Séquence)", command=lambda: run_test_in_thread(test_ww_sequence))
style_button(btn_test_ww)
btn_test_ww.pack(fill="x", pady=(0, 5))

btn_test_drills = tk.Button(frame, text="Test Perceuses (Séquence)", command=lambda: run_test_in_thread(test_perceuses))
style_button(btn_test_drills)
btn_test_drills.pack(fill="x", pady=(0, 5))

btn_all_drills = tk.Button(frame, text="Toutes Perceuses ON (200)", command=lambda: all_drills_on_thread(200))
style_button(btn_all_drills)
btn_all_drills.pack(fill="x", pady=(0, 5))
# Note: smoke_out_thread et all_drills_on_thread gèrent maintenant stop_flag.clear() en interne.

btn_smoke = tk.Button(frame, text="Test Fumée (5s)", command=lambda: smoke_out_thread(duration=5)) # smoke_out_thread gère son propre stop_flag.clear
style_button(btn_smoke)
btn_smoke.pack(fill="x", pady=(0, 5))

btn_phrases = tk.Button(frame, text="Envoyer Phrases (Morse)", command=lambda: run_test_in_thread(envoyer_phrases_origines, "A", "test.txt")) # Exemple avec soliste A et test.txt
style_button(btn_phrases)
btn_phrases.pack(fill="x", pady=(0, 5))

btn_heartbeat = tk.Button(frame, text="Test Battements Coeur (Lumières)", command=lambda: run_test_in_thread(heart_play, 20)) # 20s pour le test
style_button(btn_heartbeat)
btn_heartbeat.pack(fill="x", pady=(0, 15))


btn_lancer_routine = tk.Button(frame, text="▶ LANCER ROUTINE COMPLÈTE", command=lancer_routine_thread)
style_button(btn_lancer_routine, font=FONT_BOLD, bg_color="#28a745", fg_color="#ffffff", active_bg="#218838", bd_width=2)
btn_lancer_routine.pack(fill="x", pady=(10, 5))

btn_interrompre_routine = tk.Button(frame, text="⏹ STOP", command=interrompre_routine)
style_button(btn_interrompre_routine, font=FONT_BOLD, bg_color="#ffc107", fg_color="#212529", active_bg="#e0a800", bd_width=2)
btn_interrompre_routine.pack(fill="x", pady=(0, 5))

btn_arret_urgence = tk.Button(frame, text="🚨 ARRÊT D'URGENCE 🚨", command=arret_urgence)
style_button(btn_arret_urgence, font=FONT_BOLD, bg_color="#dc3545", fg_color="#ffffff", active_bg="#c82333", bd_width=2)
btn_arret_urgence.pack(fill="x", pady=(10, 0))

root.mainloop()
