"""Moteur de l'installation AQBTCM (routine_2026).

Toute la logique matérielle vit ici : protocole série vers les 2 ESP32
(ESP32_LIGHTS pour les bandeaux LED + la fumée, ESP32_MOTORS pour les 3
perceuses pas-à-pas), modes manuel/morse/heartbeat, orchestration de la
routine complète. Aucun code d'interface graphique - c'est routine_2026.py
qui affiche la fenêtre et appelle les méthodes de la classe Installation.
"""

import os
import re
import threading
import time

import serial
import serial.tools.list_ports
import pygame
from pygame import mixer

from play_heartbeat import HeartbeatSonifier

# ---------------- Mapping lumières (PCA9685, 15 canaux sur 16) ----------------
# 12 canaux WW (4 tubes individuels par luminaire) + 3 canaux CW (un par
# luminaire, bundle des 4 tubes câblés ensemble sur 1 seul canal MOSFET).
# Le CW reste manuel uniquement (set_channel), jamais piloté par un groupe.
LUMINAIRES = {
    "A": {"tubes": [0, 1, 2, 3]},
    "B": {"tubes": [4, 5, 6, 7]},
    "C": {"tubes": [8, 9, 10, 11]},
}
LUMINAIRES_CW = {"A": 12, "B": 13, "C": 14}
GROUPES = ["A", "B", "C"]

ID_LIGHTS = "AQBTCM_LIGHTS"
ID_MOTORS = "AQBTCM_MOTORS"


class Installation:
    def __init__(self, ecg_file="JFD_01.txt", music_file="all_new_aqbtcm.mp3"):
        self.stop_flag = threading.Event()

        self.ser_lights = None
        self.ser_motors = None
        self._lock_lights = threading.Lock()
        self._lock_motors = threading.Lock()

        self.music_file = music_file
        self.sonifier = HeartbeatSonifier(ecg_file)
        # précalcule le rendu audio en tâche de fond dès le lancement, pour
        # que le tout premier battement de cœur n'ait pas de silence pendant
        # que _render() tourne (~3.5s, mesuré sur JFD_01.txt)
        threading.Thread(target=self.sonifier.preload, daemon=True).start()

        self._smoke_stop = threading.Event()
        self._smoke_thread = None

        # réglages tunables de la routine (pas de "bonne" valeur imposée par
        # le matériel : à ajuster à l'œil / à l'oreille sur place)
        self.heartbeat_interval_s = 45
        self.heartbeat_duration_s = 15
        self.smoke_pulse_ms = 300
        self.smoke_period_ms = 4000

    # ==================== CONNEXION ====================
    def connect(self, baudrate=115200, timeout=1):
        """Scanne les ports série USB disponibles, identifie chaque ESP32 via
        la commande ID? et assigne les rôles (indépendant de l'ordre des ports,
        donc robuste au COM/tty exact du jour). Retourne (lights_ok, motors_ok)."""
        self.disconnect()
        for port in serial.tools.list_ports.comports():
            if port.vid is None:
                continue  # ignore les ports série non-USB (ex: UART GPIO du Pi)
            try:
                ser = serial.Serial(port.device, baudrate, timeout=timeout)
            except Exception as e:
                print(f"[CONNECT] {port.device} inaccessible: {e}")
                continue
            time.sleep(2)  # laisse l'ESP32 finir son reset après ouverture du port
            try:
                ser.reset_input_buffer()
                ser.write(b"ID?\n")
                time.sleep(0.3)
                reply = ser.read(ser.in_waiting or 1).decode(errors="ignore").strip()
            except Exception as e:
                print(f"[CONNECT] {port.device} erreur ID?: {e}")
                ser.close()
                continue

            if ID_LIGHTS in reply and self.ser_lights is None:
                self.ser_lights = ser
                print(f"[CONNECT] ESP32 LIGHTS sur {port.device}")
            elif ID_MOTORS in reply and self.ser_motors is None:
                self.ser_motors = ser
                print(f"[CONNECT] ESP32 MOTORS sur {port.device}")
            else:
                print(f"[CONNECT] {port.device} ne répond pas au protocole AQBTCM ({reply!r})")
                ser.close()

        return self.ser_lights is not None, self.ser_motors is not None

    def disconnect(self):
        for attr in ("ser_lights", "ser_motors"):
            ser = getattr(self, attr)
            if ser and ser.is_open:
                ser.close()
            setattr(self, attr, None)

    # ==================== ENVOI BAS NIVEAU ====================
    def _send_lights(self, cmd):
        if self.ser_lights and self.ser_lights.is_open:
            with self._lock_lights:
                try:
                    self.ser_lights.write((cmd + "\n").encode())
                except serial.SerialTimeoutException:
                    print(f"[LIGHTS] Timeout: {cmd}")
        else:
            print(f"[LIGHTS] non connecté, commande perdue: {cmd}")

    def _send_motors(self, cmd):
        if self.ser_motors and self.ser_motors.is_open:
            with self._lock_motors:
                try:
                    self.ser_motors.write((cmd + "\n").encode())
                except serial.SerialTimeoutException:
                    print(f"[MOTORS] Timeout: {cmd}")
        else:
            print(f"[MOTORS] non connecté, commande perdue: {cmd}")

    # ==================== LUMIÈRES : MANUEL ====================
    def set_channel(self, canal, valeur):
        valeur = max(0, min(255, int(valeur)))
        self._send_lights(f"P{canal}:{valeur}")

    def set_group(self, groupe, valeur):
        for canal in LUMINAIRES[groupe]["tubes"]:
            self.set_channel(canal, valeur)

    def set_cw(self, groupe, valeur):
        """CW (blanc froid) du luminaire — manuel uniquement, jamais piloté
        par le morse/heartbeat (voir mapping en tête de fichier)."""
        self.set_channel(LUMINAIRES_CW[groupe], valeur)

    def all_lights_off(self):
        for groupe in GROUPES:
            self.set_group(groupe, 0)
            self.set_cw(groupe, 0)

    def test_ww_sequence(self):
        print("Test WW séquentiel (fade A->B->C)")
        for _ in range(2):
            for groupe in GROUPES:
                if self.stop_flag.is_set():
                    print("Test WW interrompu")
                    return
                for lvl in range(0, 256, 32):
                    if self.stop_flag.is_set():
                        return
                    self.set_group(groupe, lvl)
                    time.sleep(0.05)
                time.sleep(0.2)
                for lvl in reversed(range(0, 256, 32)):
                    if self.stop_flag.is_set():
                        return
                    self.set_group(groupe, lvl)
                    time.sleep(0.05)
                time.sleep(0.1)
        print("Fin test WW")

    def test_cw_sequence(self):
        print("Test CW séquentiel (fade A->B->C)")
        for groupe in GROUPES:
            if self.stop_flag.is_set():
                print("Test CW interrompu")
                return
            for lvl in range(0, 256, 32):
                if self.stop_flag.is_set():
                    return
                self.set_cw(groupe, lvl)
                time.sleep(0.05)
            time.sleep(0.2)
            for lvl in reversed(range(0, 256, 32)):
                if self.stop_flag.is_set():
                    return
                self.set_cw(groupe, lvl)
                time.sleep(0.05)
            time.sleep(0.1)
        print("Fin test CW")

    # ==================== LUMIÈRES : MORSE ====================
    def _attendre_ok(self, timeout=145):
        if not self.ser_lights or not self.ser_lights.is_open:
            return False
        start = time.time()
        buffer = ""
        while time.time() - start < timeout:
            if self.stop_flag.is_set():
                print("Attente OK interrompue")
                return False
            if self.ser_lights.in_waiting > 0:
                buffer += self.ser_lights.read(self.ser_lights.in_waiting).decode(errors="ignore")
                if "OK" in buffer:
                    return True
            time.sleep(0.05)
        print("Timeout attente OK de l'ESP32 LIGHTS")
        return False

    def envoyer_phrases_origines(self, soliste="A", fichier="test.txt"):
        if not os.path.exists(fichier):
            print(f"Fichier {fichier} introuvable.")
            return
        with open(fichier, "r", encoding="utf-8") as f:
            texte = f.read()

        phrases = [p.strip() for p in re.split(r"\.\s*", texte) if p.strip()]
        print(f"{len(phrases)} phrases extraites du fichier.")

        for phrase in phrases:
            if self.stop_flag.is_set():
                print("Envoi phrases interrompu")
                return
            match = re.search(r"\*(.+?)\*", phrase)
            if match:
                mot_choeur = match.group(1)
                phrase_nettoyee = phrase.replace(f"*{mot_choeur}*", mot_choeur)
            else:
                mot_choeur = ""
                phrase_nettoyee = phrase

            cmd = f"M:{soliste}|{phrase_nettoyee}|*{mot_choeur}*"
            self._send_lights(cmd)
            print(f"Envoyé: {cmd}")

            if not self._attendre_ok():
                print("Pas de réponse OK, arrêt de l'envoi.")
                break

        print("Fin de l'envoi des phrases.")

    # ==================== MOTEURS (perceuses) ====================
    def drill_start(self, drill_id):
        self._send_motors(f"D{drill_id}:START")

    def drill_stop(self, drill_id):
        self._send_motors(f"D{drill_id}:STOP")

    def drills_start_all(self):
        self._send_motors("D:ALL:START")

    def drills_stop_all(self):
        self._send_motors("D:ALL:STOP")

    def test_perceuse(self, drill_id, duree_s=5):
        """Démarre une perceuse seule pendant duree_s, interruptible."""
        print(f"Test perceuse {drill_id} ({duree_s}s)")
        self.drill_start(drill_id)
        start = time.time()
        while time.time() - start < duree_s:
            if self.stop_flag.is_set():
                break
            time.sleep(0.1)
        self.drill_stop(drill_id)
        print(f"Fin test perceuse {drill_id}")

    def test_perceuses_sequentiel(self, duree_s=5):
        print("Test perceuses (une par une)")
        for drill_id in range(3):
            if self.stop_flag.is_set():
                print("Test perceuses interrompu")
                return
            self.test_perceuse(drill_id, duree_s)
            time.sleep(0.5)
        print("Fin test perceuses")

    # ==================== FUMÉE ====================
    def smoke_pulse(self, pulse_ms=None, period_ms=None, repeats=1):
        """Déclenche des impulsions de fumée. repeats=0 -> continue jusqu'à
        smoke_stop(). Le timing (durée/fréquence) reste ajustable ici, côté
        Python, sans reflasher le firmware - pensé pour un réglage à l'œil sur
        place."""
        pulse_ms = self.smoke_pulse_ms if pulse_ms is None else pulse_ms
        period_ms = self.smoke_period_ms if period_ms is None else period_ms

        def _run():
            n = 0
            while not self._smoke_stop.is_set() and not self.stop_flag.is_set():
                self._send_lights("FUM_ON")
                self._smoke_stop.wait(pulse_ms / 1000)
                self._send_lights("FUM_OFF")
                n += 1
                if repeats and n >= repeats:
                    break
                self._smoke_stop.wait(max(0, (period_ms - pulse_ms) / 1000))

        self._smoke_stop.clear()
        self._smoke_thread = threading.Thread(target=_run, daemon=True)
        self._smoke_thread.start()

    def smoke_stop(self):
        self._smoke_stop.set()
        self._send_lights("FUM_OFF")

    # ==================== MUSIQUE ====================
    def init_music(self):
        if not mixer.get_init():
            mixer.init()

    def music_start(self, volume=0.6):
        if not os.path.exists(self.music_file):
            print(f"Fichier audio manquant: {self.music_file}")
            return
        self.init_music()
        mixer.music.load(self.music_file)
        mixer.music.set_volume(volume)
        mixer.music.play()
        print("Musique lancée")

    def music_stop(self, fade_ms=3333):
        if mixer.get_init():
            mixer.music.fadeout(fade_ms)
            print("Musique stoppée")

    # ==================== BATTEMENT DE CŒUR ====================
    def run_heartbeat_sequence(self, duration_s=None, update_hz=25):
        """Interrompt/suspend les 2 ESP32 en même temps, joue le son en live
        (HeartbeatSonifier) et anime les lumières en phase avec lui."""
        duration_s = self.heartbeat_duration_s if duration_s is None else duration_s
        print("Début séquence battement de cœur")

        self._send_motors("H:START")
        self._send_lights("H:START")
        self.sonifier.start()
        try:
            start = time.time()
            while time.time() - start < duration_s:
                if self.stop_flag.is_set():
                    break
                env = self.sonifier.get_current_envelope()
                self._send_lights(f"H:{int(env * 255)}")
                time.sleep(1 / update_hz)
        finally:
            self.sonifier.stop()
            self._send_lights("H:STOP")
            self._send_motors("H:STOP")
        print("Fin séquence battement de cœur")

    def run_heartbeat_sequence_thread(self, duration_s=None):
        threading.Thread(
            target=self.run_heartbeat_sequence, args=(duration_s,), daemon=True
        ).start()

    # ==================== ARRÊT D'URGENCE ====================
    def arret_urgence(self):
        print("⚠️ ARRÊT D'URGENCE ⚠️")
        self.stop_flag.set()
        if mixer.get_init():
            mixer.music.stop()  # coupure instantanée voulue pour l'urgence, pas de fondu
        self.sonifier.stop(fade_ms=0)  # idem
        self.smoke_stop()
        self.drills_stop_all()
        self.all_lights_off()
        print("Tous les systèmes ont été mis hors tension.")

    # ==================== ROUTINE COMPLÈTE ====================
    def routine(self):
        self.stop_flag.clear()
        print("Routine lancée.")

        self.smoke_pulse(repeats=0)
        self.music_start(volume=0.8)
        self.drills_start_all()
        time.sleep(3)

        t_phrases = threading.Thread(
            target=self.envoyer_phrases_origines, args=("B", "hesiode.txt")
        )
        t_phrases.start()

        derniere_pulsation = time.time()
        while t_phrases.is_alive():
            if self.stop_flag.is_set():
                break
            if time.time() - derniere_pulsation >= self.heartbeat_interval_s:
                self.run_heartbeat_sequence()
                derniere_pulsation = time.time()
            time.sleep(0.5)

        self.smoke_stop()
        self.drills_stop_all()
        self.music_stop()
        print("Fin de routine.")

    def routine_thread(self):
        threading.Thread(target=self.routine, daemon=True).start()

    def interrompre_routine(self):
        self.stop_flag.set()
        self.music_stop()
        self.smoke_stop()
        print("Signal d'interruption envoyé.")
