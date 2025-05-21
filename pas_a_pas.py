import tkinter as tk
import pygame
import serial
import time
import sys

# Initialisation de pygame pour la musique
pygame.mixer.init()

# Classe personnalisée pour rediriger les prints vers la console et le widget Text
class RedirectText:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        # Afficher le message dans la fenêtre Tkinter
        self.text_widget.config(state=tk.NORMAL)  # Permet de modifier le texte
        self.text_widget.insert(tk.END, message)
        self.text_widget.yview(tk.END)  # Faire défiler vers le bas pour voir le dernier message
        self.text_widget.config(state=tk.DISABLED)  # Désactive la modification par l'utilisateur
        # Afficher également dans la console
        sys.__stdout__.write(message)

# Fonction pour démarrer la musique
def music_start():
    pygame.mixer.music.load("all_new_aqbtcm.mp3")
    pygame.mixer.music.set_volume(0.2)
    pygame.mixer.music.play(fade_ms=5000)
    print("Musique démarrée")

# Fonction pour arrêter la musique
def music_stop():
    pygame.mixer.music.fadeout(5000)
    print("Musique arrêtée")

# Fonction pour tester la musique (si tu veux une action spécifique ici)
def music_test():
    print("Test de la musique en cours...")

# Fonction pour allumer tous les néons
def neons_all_on():
    print("Tous les néons allumés")

# Fonction pour éteindre tous les néons
def neons_all_off():
    print("Tous les néons éteints")

# Fonction pour activer/désactiver la perceuse
def drill_on_and_off():
    print("Perceuse allumée ou éteinte")

# Vérifier la connexion Arduino
def check_arduino_connection():
    try:
        # Essaie de te connecter à l'Arduino via le port série (exemple)
        arduino = serial.Serial('COM3', 9600, timeout=1)  # Adapte le port à ton système
        time.sleep(2)  # Attends que l'arduino soit prêt
        arduino.close()  # Ferme la connexion une fois la vérification faite
        return True  # Arduino connecté
    except serial.SerialException:
        return False  # Pas de connexion à l'Arduino

# Fonction qui démarre la boucle si l'Arduino est connecté
def start_loop():
    if check_arduino_connection():
        print("Arduino connecté, lancement de la boucle")
        # Lancer la logique de la boucle avec Arduino ici
        # Ex: init_arduino_loop()
    else:
        print("Erreur: Arduino non connecté ! La boucle ne peut pas démarrer.")

# Fonction pour tester la connexion Arduino
def test_arduino_connection():
    if check_arduino_connection():
        print("Connexion Arduino réussie !")
    else:
        print("Erreur de connexion : Arduino non trouvé.")

# Créer la fenêtre Tkinter
if __name__ == '__main__':
    root = tk.Tk()
    root.title("Arduino Controller")
    root.geometry("400x400")
    root.config(bg="#f0f0f0")

    # Créer le cadre pour les boutons
    frame = tk.Frame(root, bg="#f0f0f0")
    frame.pack(pady=20)

    # Ajouter les boutons
    tk.Button(frame, text="Start Music", command=music_start, width=20).pack(pady=5)
    tk.Button(frame, text="Stop Music", command=music_stop, width=20).pack(pady=5)
    tk.Button(frame, text="Test Music", command=music_test, width=20).pack(pady=5)
    tk.Button(frame, text="Neons All On", command=neons_all_on, width=20).pack(pady=5)
    tk.Button(frame, text="Neons All Off", command=neons_all_off, width=20).pack(pady=5)
    tk.Button(frame, text="Drill On and Off", command=drill_on_and_off, width=20).pack(pady=5)
    tk.Button(frame, text="Test Arduino Connection", command=test_arduino_connection, width=20).pack(pady=5)
    tk.Button(frame, text="Start Arduino Loop", command=start_loop, width=20).pack(pady=5)

    # Créer un cadre pour afficher les messages
    output_frame = tk.Frame(root, bg="#e0e0e0", relief="sunken", width=350, height=150)
    output_frame.pack(pady=20)

    # Ajouter un widget Text pour afficher les messages
    output_text = tk.Text(output_frame, height=8, width=40, wrap=tk.WORD)
    output_text.pack(padx=10, pady=10)
    output_text.config(state=tk.DISABLED)  # Empêche l'utilisateur de modifier directement le texte

    # Rediriger les prints vers la fois la console et le widget Text
    sys.stdout = RedirectText(output_text)

    # Démarrer l'interface graphique
    root.mainloop()
