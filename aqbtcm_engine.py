"""Moteur de l'installation AQBTCM (routine_2026).

Toute la logique matérielle vit ici : protocole série vers les 2 ESP32
(ESP32_LIGHTS pour les bandeaux LED + la fumée, ESP32_MOTORS pour les 3
perceuses pas-à-pas), modes manuel/morse/heartbeat, orchestration de la
routine complète. Aucun code d'interface graphique - c'est routine_2026.py
qui affiche la fenêtre et appelle les méthodes de la classe Installation.
"""

import os
import random
import re
import threading
import time
import unicodedata

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

def sans_accents(texte):
    """Le firmware ne connaît que A-Z et 0-9 : é -> e, œ -> oe, ç -> c..."""
    texte = (texte.replace("œ", "oe").replace("Œ", "OE")
                  .replace("æ", "ae").replace("Æ", "AE"))
    return "".join(c for c in unicodedata.normalize("NFD", texte) if not unicodedata.combining(c))


ID_LIGHTS = "AQBTCM_LIGHTS"
ID_MOTORS = "AQBTCM_MOTORS"


class Installation:
    def __init__(self, ecg_file="JFD_01.txt", music_file="aqbtcm+drone_neo.wav"):
        self.stop_flag = threading.Event()
        self._heartbeat_active = threading.Event()

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
        self.heartbeat_every_s = 300            # battement toutes les 5 min de lecture
        self.heartbeat_duration_s = 30          # durée du battement (son + lumière)
        self.heartbeat_music_fade_s = 4         # descente / remontée de la musique autour du battement
        self.heartbeat_silence_after_s = 3      # noir et silence entre la fin du battement et la reprise
        self.lights_fade_out_ms = 6000          # descente des lumières vers le noir avant le battement
        self.morse_start_delay_s = 10           # temps de musique seule avant que la lecture commence
        # chaque perceuse démarre à un instant tiré au hasard dans cette
        # fenêtre (en s après le début de la routine) : elles peuvent partir
        # ensemble ou décalées, sans ordre imposé
        self.perceuses_start_min_s = 10
        self.perceuses_start_max_s = 40
        self.music_volume = 0.6
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
                ser.write(b"\nID?\n")  # le \n vide un éventuel octet parasite à l'ouverture du port
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
    def raw_lights(self, cmd):
        """Envoi direct d'une commande brute à l'ESP32 LIGHTS (bench test)."""
        self._send_lights(cmd)

    def raw_motors(self, cmd):
        """Envoi direct d'une commande brute à l'ESP32 MOTORS (bench test)."""
        self._send_motors(cmd)

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

    def lights_fade_out(self, duree_ms=None):
        """Fait redescendre en douceur vers le noir ce qui est allumé côté
        morse (soliste + chœurs), au lieu de la coupure sèche d'avant. Le
        fondu est calculé par l'ESP32 (non bloquant de son côté) ; ici on
        attend juste qu'il ait fini."""
        duree_ms = self.lights_fade_out_ms if duree_ms is None else duree_ms
        self._send_lights(f"F:{int(duree_ms)}")
        self.stop_flag.wait(duree_ms / 1000)

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
    def _attendre_ok(self, timeout):
        """Attend la fin du morse d'une phrase. Retourne "ok", "erreur" (l'ESP
        a refusé la commande), "interrompu" (battement de cœur en cours),
        "redemarre" (l'ESP a rebooté en pleine phrase — inutile d'attendre le
        timeout complet), "stop" ou "timeout"."""
        if not self.ser_lights or not self.ser_lights.is_open:
            return "timeout"
        start = time.time()
        buffer = ""
        while time.time() - start < timeout:
            if self.stop_flag.is_set():
                return "stop"
            if self._heartbeat_active.is_set():
                return "interrompu"
            if self.ser_lights.in_waiting > 0:
                buffer += self.ser_lights.read(self.ser_lights.in_waiting).decode(errors="ignore")
                if "ERR_FORMAT_M" in buffer:
                    return "erreur"
                if "OK" in buffer:
                    return "ok"
                # l'ESP annonce ce message à chaque démarrage (voir esp32_lights.ino) :
                # s'il apparaît ici, c'est qu'il a rebooté en cours de phrase (plus la
                # peine d'attendre les minutes restantes du timeout pour rien)
                if "AQBTCM_LIGHTS" in buffer:
                    return "redemarre"
            time.sleep(0.05)
        return "timeout"

    def envoyer_phrases_origines(self, soliste="ABC", fichier="test.txt"):
        """Lit le fichier phrase par phrase en morse. `soliste` est la suite des
        groupes qui se relaient : "ABC" = le soliste change à chaque phrase
        (A, B, C, A...), "B" = toujours B. Si un battement de cœur survient
        pendant une phrase (déclenché par la routine, au temps), l'attente est
        coupée et la phrase est relue depuis son début une fois le battement
        fini : la lecture reprend donc là où elle en était."""
        if not os.path.exists(fichier):
            print(f"Fichier {fichier} introuvable.")
            return
        with open(fichier, "r", encoding="utf-8") as f:
            texte = f.read()

        phrases = [p.strip() for p in re.split(r"\.\s*", texte) if p.strip()]
        print(f"{len(phrases)} phrases extraites du fichier.")

        i = 0
        tentatives_redemarrage = 0
        while i < len(phrases):
            if self.stop_flag.is_set():
                print("Envoi phrases interrompu")
                return
            # un battement de cœur est en cours : on attend sa fin avant de (re)lire
            while self._heartbeat_active.is_set() and not self.stop_flag.is_set():
                time.sleep(0.1)

            # les *mots marqués* restent dans la phrase : le firmware sait ainsi
            # à quel moment de la lecture les chœurs doivent les reprendre
            # un retour à la ligne interne couperait la commande en deux côté ESP
            phrase = " ".join(sans_accents(phrases[i]).split())
            phrase_nettoyee = phrase.replace("*", "")

            cmd = f"M:{soliste[i % len(soliste)]}|{phrase}"
            if self.ser_lights and self.ser_lights.is_open:
                with self._lock_lights:
                    self.ser_lights.reset_input_buffer()  # purge les anciens "OK" (ex: commandes P)
            self._send_lights(cmd)
            print(f"Envoyé ({i + 1}/{len(phrases)}): {phrase_nettoyee[:60]}")

            # le morse dure environ 1.5 s par caractère : large marge avant de conclure à un blocage
            resultat = self._attendre_ok(timeout=60 + 3 * len(phrase_nettoyee))
            if resultat == "ok":
                i += 1
                tentatives_redemarrage = 0
            elif resultat == "interrompu":
                print("Lecture interrompue par le battement de cœur, la phrase sera relue.")
            elif resultat == "erreur":
                print(f"L'ESP32 LIGHTS a refusé la phrase {i + 1}, on passe à la suivante.")
                i += 1
                tentatives_redemarrage = 0
            elif resultat == "redemarre":
                tentatives_redemarrage += 1
                if tentatives_redemarrage > 5:
                    print("L'ESP32 LIGHTS redémarre en boucle, arrêt de l'envoi.")
                    break
                print(f"L'ESP32 LIGHTS a redémarré en pleine phrase {i + 1}, on la relit "
                      f"(essai {tentatives_redemarrage}/5).")
                time.sleep(1)  # laisse l'ESP finir son setup() avant de renvoyer
            elif resultat == "stop":
                print("Envoi phrases interrompu")
                return
            else:
                print("Pas de réponse OK de l'ESP32 LIGHTS, arrêt de l'envoi.")
                break

        print("Fin de l'envoi des phrases.")

    # ==================== MOTEURS (perceuses) ====================
    def drill_start(self, drill_num):
        """drill_num : 1, 2 ou 3 — même numéro que le bouton "Perceuse N" du
        GUI et que le protocole série (D1/D2/D3), pour ne plus jamais avoir
        de décalage entre l'affichage, le câblage et le code."""
        self._send_motors(f"D{drill_num}:START")

    def drill_stop(self, drill_num):
        self._send_motors(f"D{drill_num}:STOP")

    def drills_start_all(self):
        self._send_motors("D:ALL:START")

    def drills_stop_all(self):
        self._send_motors("D:ALL:STOP")

    def demarrer_perceuses_aleatoire(self):
        """Lance les 3 perceuses à des instants tirés au hasard dans la fenêtre
        [perceuses_start_min_s, perceuses_start_max_s] : elles peuvent partir
        ensemble ou décalées, sans ordre imposé. Une fois lancée, chaque
        perceuse enchaîne toute seule ses cycles côté firmware — rien d'autre
        à envoyer jusqu'au battement de cœur."""
        for drill_num in (1, 2, 3):
            delai = random.uniform(self.perceuses_start_min_s, self.perceuses_start_max_s)
            threading.Thread(
                target=self._demarrer_perceuse_apres,
                args=(drill_num, delai),
                daemon=True,
            ).start()

    def _demarrer_perceuse_apres(self, drill_num, delai_s):
        if self.stop_flag.wait(delai_s):
            return  # arrêt demandé avant que cette perceuse ait démarré
        print(f"Perceuse {drill_num} démarre (t+{delai_s:.0f}s)")
        self.drill_start(drill_num)

    def test_perceuse(self, drill_num, duree_s=5):
        """Démarre une perceuse seule pendant duree_s, interruptible."""
        print(f"Test perceuse {drill_num} ({duree_s}s)")
        self.drill_start(drill_num)
        start = time.time()
        while time.time() - start < duree_s:
            if self.stop_flag.is_set():
                break
            time.sleep(0.1)
        self.drill_stop(drill_num)
        print(f"Fin test perceuse {drill_num}")

    def test_perceuses_sequentiel(self, duree_s=5):
        print("Test perceuses (une par une)")
        for drill_num in (1, 2, 3):
            if self.stop_flag.is_set():
                print("Test perceuses interrompu")
                return
            self.test_perceuse(drill_num, duree_s)
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
        self.music_volume = volume
        mixer.music.load(self.music_file)
        mixer.music.set_volume(volume)
        mixer.music.play()
        print("Musique lancée")

    def _fondu_musique(self, volume_cible, duree_s):
        """Fait glisser le volume de la musique vers volume_cible en duree_s
        secondes (interruptible par stop_flag)."""
        if not mixer.get_init():
            return
        depart = mixer.music.get_volume()
        pas = max(1, int(duree_s * 20))
        for k in range(1, pas + 1):
            if self.stop_flag.is_set():
                return
            mixer.music.set_volume(depart + (volume_cible - depart) * k / pas)
            time.sleep(duree_s / pas)

    def music_stop(self, fade_ms=3333):
        if mixer.get_init():
            mixer.music.fadeout(fade_ms)
            print("Musique stoppée")

    # ==================== BATTEMENT DE CŒUR ====================
    def run_heartbeat_sequence(self, duration_s=None, update_hz=25):
        """Interruption battement de cœur :
        1. les perceuses s'arrêtent et les lumières s'éteignent (fin de la lecture morse)
        2. la musique descend jusqu'au silence
        3. le cœur bat, en son (HeartbeatSonifier) et en lumière, pendant duration_s
        4. tout s'éteint, un temps de noir et de silence
        5. les perceuses repartent, la musique remonte, et l'appelant reprend la lecture
        """
        duration_s = self.heartbeat_duration_s if duration_s is None else duration_s
        print("Début séquence battement de cœur")

        musique_jouait = mixer.get_init() and mixer.music.get_busy()
        volume_musique = self.music_volume

        self._heartbeat_active.set()
        try:
            self._send_motors("H:START")
            self.lights_fade_out()    # descente douce de ce qui est allumé vers le noir
            self._send_lights("H:0")  # entre en mode battement, déjà au noir : coupe morse et chœurs

            if musique_jouait:
                self._fondu_musique(0.0, self.heartbeat_music_fade_s)
                mixer.music.pause()

            if not self.stop_flag.is_set():
                self.sonifier.start()
                start = time.time()
                while time.time() - start < duration_s:
                    if self.stop_flag.is_set():
                        break
                    env = self.sonifier.get_current_envelope()
                    self._send_lights(f"H:{int(env * 255)}")
                    time.sleep(1 / update_hz)
                self.sonifier.stop()

            self._send_lights("H:STOP")  # tout s'éteint
            if not self.stop_flag.is_set():
                self.stop_flag.wait(self.heartbeat_silence_after_s)
        finally:
            self.sonifier.stop(fade_ms=0)
            self._send_lights("H:STOP")
            self._send_motors("H:STOP")
            if musique_jouait and not self.stop_flag.is_set():
                # la musique remonte en tâche de fond, pendant que la lecture reprend
                mixer.music.unpause()
                threading.Thread(
                    target=self._fondu_musique,
                    args=(volume_musique, self.heartbeat_music_fade_s),
                    daemon=True,
                ).start()
            self._heartbeat_active.clear()
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
        """Déroulé complet, en boucle jusqu'à interruption :

        1. la musique part seule
        2. les 3 perceuses démarrent chacune à un instant tiré au hasard, et
           la lecture morse commence après morse_start_delay_s
        3. toutes les heartbeat_every_s, tout s'interrompt pour le battement
           de cœur : perceuses en pause, fondu des lumières vers le noir,
           battement, silence
        4. tout reprend où il en était (perceuses dans leur cycle, morse à la
           phrase interrompue, musique qui remonte) — et on repart pour un tour
        """
        self.stop_flag.clear()
        print("Routine lancée.")

        self.smoke_pulse(repeats=0)
        self.music_start(volume=0.8)
        self.demarrer_perceuses_aleatoire()

        if not self.stop_flag.wait(self.morse_start_delay_s):
            t_phrases = threading.Thread(
                target=self.envoyer_phrases_origines,
                args=("ABC", "hesiode.txt"),
                daemon=True,
            )
            t_phrases.start()

            while t_phrases.is_alive():
                # une tranche de lecture, puis on coupe tout pour le battement
                if self.stop_flag.wait(self.heartbeat_every_s):
                    break
                if not t_phrases.is_alive():
                    break
                self.run_heartbeat_sequence()

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
