import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports

def connecter_arduinos():
    try:
        mega_light_1 = serial.Serial('COM8', 115200, timeout=1)
        print("Arduino MEGA LIGHT 1 connected")
    except Exception as e:
        print(f"Failed to connect to Arduino MEGA 1 (Light A+B): {e}")
    
    try:
        mega_light_2 = serial.Serial('COM9', 115200, timeout=1)
        print("Arduino MEGA LIGHT 2 connected")
    except Exception as e:
        print(f"Failed to connect to Arduino MEGA 2 (Light B+C): {e}")

    try:
        uno_drill = serial.Serial('COM10', 115200, timeout=1)
        print("Arduino UNO DRILL connected")
    except Exception as e:
        print(f"Failed to connect to Arduino UNO DRILL (Light D + Drills 1+2+3): {e}")

    # Ici tu pourras continuer ta logique avec mega_light_1, mega_light_2, uno_drill

def lancer_routine():
    # Exemple d'action lancée par le bouton
    connecter_arduinos()
    messagebox.showinfo("Info", "Routine lancée, voir console.")

# Création de la fenêtre principale
root = tk.Tk()
root.title("Contrôle Arduino")

# Bouton pour lancer la routine
btn_lancer = tk.Button(root, text="Lancer routine", command=lancer_routine)
btn_lancer.pack(padx=20, pady=20)

root.mainloop()
