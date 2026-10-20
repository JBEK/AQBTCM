"""Appli de l'installation AQBTCM : la fenêtre du quotidien, lancée depuis
l'icône du bureau.

Se connecte toute seule aux deux ESP32 à l'ouverture et affiche leur état en
permanence. Quatre boutons seulement : lancer, éteindre, arrêt d'urgence, et
reconnecter les cartes. Les boutons de test restent dans routine_2026.py.

Lancée sans terminal, l'appli recopie tout ce que le moteur affiche (print)
dans la zone du bas et dans aqbtcm.log, pour garder une trace en cas de souci.
"""

import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox

DOSSIER = os.path.dirname(os.path.abspath(__file__))
os.chdir(DOSSIER)  # le moteur ouvre ses fichiers (mp3, textes, réglages) en relatif

FICHIER_LOG = os.path.join(DOSSIER, "aqbtcm.log")
VERT, ROUGE, ORANGE, GRIS = "#2e7d32", "#c62828", "#ef6c00", "#757575"
FOND = "#f4f4f4"


class Journal:
    """Remplace sys.stdout/stderr : chaque écriture part dans le fichier de log
    et dans une file que la boucle Tk vide (les print arrivent des threads du
    moteur, et seul le thread Tk a le droit de toucher aux widgets)."""

    def __init__(self, fichier):
        self.fichier = open(fichier, "a", encoding="utf-8", buffering=1)
        self.file = queue.Queue()

    def write(self, texte):
        self.fichier.write(texte)
        if texte:
            self.file.put(texte)

    def vider_dans(self, zone):
        morceaux = []
        while not self.file.empty():
            morceaux.append(self.file.get_nowait())
        if not morceaux:
            return
        zone.configure(state="normal")
        zone.insert("end", "".join(morceaux))
        # garde les 500 dernières lignes : l'installation tourne des heures
        if int(zone.index("end-1c").split(".")[0]) > 500:
            zone.delete("1.0", "100.0")
        zone.see("end")
        zone.configure(state="disabled")

    def flush(self):
        self.fichier.flush()


journal = Journal(FICHIER_LOG)
sys.stdout = sys.stderr = journal

from aqbtcm_engine import Installation  # noqa: E402  (après la redirection : ses print sont capturés)

install = Installation()
connexion_en_cours = threading.Event()


# ---------------- actions ----------------
def connecter():
    """Cherche les deux ESP32 en tâche de fond (quelques secondes : chaque
    carte redémarre à l'ouverture de son port)."""
    if connexion_en_cours.is_set():
        return
    connexion_en_cours.set()
    for lbl in (lbl_lights, lbl_motors):
        lbl.config(text=lbl.nom + " : recherche…", fg=ORANGE)

    def _run():
        try:
            install.connect()
        finally:
            connexion_en_cours.clear()

    threading.Thread(target=_run, daemon=True).start()


def reconnecter():
    if install.routine_en_cours:
        messagebox.showwarning(
            "Routine en cours",
            "Éteins d'abord l'installation : reconnecter redémarre les deux cartes.",
        )
        return
    connecter()


def lancer():
    if install.routine_en_cours:
        return
    if install.verrouille:
        if not messagebox.askyesno(
            "Arrêt d'urgence actif",
            "Un arrêt d'urgence a été déclenché.\nTout est vérifié, on relance ?",
        ):
            return
        install.rearmer()
    lights_ok, motors_ok = install.etat_connexions()
    if not (lights_ok and motors_ok):
        manquantes = " et ".join(n for n, ok in (("LIGHTS", lights_ok), ("MOTORS", motors_ok)) if not ok)
        if not messagebox.askyesno(
            "Carte non connectée",
            f"{manquantes} non connectée.\nLancer quand même ?",
        ):
            return
    install.routine_thread()


def eteindre():
    if install.routine_en_cours:
        install.interrompre_routine()


def arret_urgence():
    install.arret_urgence()


def fermer():
    if install.routine_en_cours and not messagebox.askyesno(
        "Routine en cours", "L'installation tourne. Tout éteindre et fermer ?"
    ):
        return
    install.arret_urgence()
    install.disconnect()
    racine.destroy()


# ---------------- affichage de l'état ----------------
def rafraichir():
    """Toutes les secondes : état des cartes, de la routine, et des boutons."""
    if not connexion_en_cours.is_set():
        for lbl, ok in zip((lbl_lights, lbl_motors), install.etat_connexions()):
            lbl.config(text=lbl.nom + (" : connectée" if ok else " : non connectée"),
                       fg=VERT if ok else ROUGE)

    if install.verrouille:
        lbl_etat.config(text="ARRÊT D'URGENCE", fg=ROUGE)
    elif install.routine_en_cours:
        lbl_etat.config(text="Installation en marche", fg=VERT)
    else:
        lbl_etat.config(text="À l'arrêt", fg=GRIS)

    en_marche = install.routine_en_cours
    btn_lancer.config(state="disabled" if en_marche else "normal")
    btn_eteindre.config(state="normal" if en_marche else "disabled")
    btn_reconnecter.config(
        state="disabled" if en_marche or connexion_en_cours.is_set() else "normal")
    racine.after(1000, rafraichir)


# ---------------- fenêtre ----------------
racine = tk.Tk(className="aqbtcm")  # className = StartupWMClass du .desktop (icône dans le dock)
racine.title("AQBTCM")
racine.geometry("460x620")
racine.minsize(380, 480)
racine.configure(bg=FOND)
racine.protocol("WM_DELETE_WINDOW", fermer)
try:
    racine.iconphoto(True, tk.PhotoImage(file=os.path.join(DOSSIER, "aqbtcm_icon.png")))
except tk.TclError:
    pass

POLICE = ("Helvetica", 12)
POLICE_GRANDE = ("Helvetica", 16, "bold")


def bouton(texte, commande, fond, police=POLICE_GRANDE, hauteur=2):
    b = tk.Button(racine, text=texte, command=commande, font=police, bg=fond, fg="white",
                  activebackground=fond, activeforeground="white", disabledforeground="#dddddd",
                  relief="raised", bd=2, height=hauteur, cursor="hand2")
    b.pack(fill="x", padx=20, pady=6)
    return b


tk.Label(racine, text="À quoi bon tous ces mots autour du chêne et du rocher",
         font=("Helvetica", 11, "italic"), bg=FOND, fg=GRIS, wraplength=420).pack(pady=(14, 4))

cadre_cartes = tk.Frame(racine, bg=FOND)
cadre_cartes.pack(fill="x", padx=20, pady=4)
lbl_lights = tk.Label(cadre_cartes, font=POLICE, bg=FOND)
lbl_lights.nom = "LIGHTS"
lbl_lights.pack(side="left", expand=True)
lbl_motors = tk.Label(cadre_cartes, font=POLICE, bg=FOND)
lbl_motors.nom = "MOTORS"
lbl_motors.pack(side="right", expand=True)

lbl_etat = tk.Label(racine, font=POLICE_GRANDE, bg=FOND)
lbl_etat.pack(pady=(6, 8))

btn_lancer = bouton("Lancer", lancer, VERT)
btn_eteindre = bouton("Éteindre", eteindre, "#455a64")
btn_urgence = bouton("ARRÊT D'URGENCE", arret_urgence, ROUGE, hauteur=3)
btn_reconnecter = bouton("Reconnecter les cartes", reconnecter, "#5c6bc0",
                         police=("Helvetica", 11, "bold"), hauteur=1)

zone_log = tk.Text(racine, height=8, font=("Monospace", 9), bg="#263238", fg="#cfd8dc",
                   state="disabled", wrap="word", bd=0)
zone_log.pack(fill="both", expand=True, padx=20, pady=(10, 16))


def afficher_journal():
    journal.vider_dans(zone_log)
    racine.after(200, afficher_journal)


connecter()
rafraichir()
afficher_journal()

if __name__ == "__main__":
    racine.mainloop()
