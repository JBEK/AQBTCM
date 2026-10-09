"""Moteur de l'installation AQBTCM (routine_2026).

Toute la logique matérielle vit ici : protocole série vers les 2 ESP32
(ESP32_LIGHTS pour les bandeaux LED + la fumée, ESP32_MOTORS pour les 3
perceuses pas-à-pas), modes manuel/morse/heartbeat, orchestration de la
routine complète. Aucun code d'interface graphique - c'est routine_2026.py
qui affiche la fenêtre et appelle les méthodes de la classe Installation.
"""

import inspect
import json
import math
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


REGLAGES_SON_COEUR = "heartbeat_settings.json"


def _reglages_son_coeur():
    """Réglages du son du cœur validés dans heartbeat_tuner.py, s'il y en a.
    Seuls les paramètres que HeartbeatSonifier connaît encore sont gardés : un
    fichier enregistré avec une ancienne version ne doit pas empêcher le
    démarrage. Le calage lub-dub n'en fait pas partie, il suit la lumière."""
    try:
        with open(REGLAGES_SON_COEUR, encoding="utf-8") as f:
            reglages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    connus = inspect.signature(HeartbeatSonifier.__init__).parameters
    return {k: v for k, v in reglages.items()
            if k in connus and k not in ("ecg_file", "lub_dub_s", "lub_align_s")}


ID_LIGHTS = "AQBTCM_LIGHTS"
ID_MOTORS = "AQBTCM_MOTORS"


class Installation:
    def __init__(self, ecg_file="INES_02.txt", music_file="aqbtcm_track.mp3"):
        self.stop_flag = threading.Event()
        self._heartbeat_active = threading.Event()

        self.ser_lights = None
        self.ser_motors = None
        self._lock_lights = threading.Lock()
        self._lock_motors = threading.Lock()

        self.music_file = music_file

        self._smoke_stop = threading.Event()
        self._smoke_thread = None

        # Un arrêt d'urgence reste VERROUILLÉ : tant que ce drapeau est posé,
        # aucune action ne redémarre, et seul un réarmement explicite le lève.
        # Sans ça, n'importe quel bouton de test rabaissait stop_flag et les
        # threads encore en attente (perceuses, fumée) repartaient tout seuls.
        self._verrouille = False
        # gardes de réentrance : un seul déroulé et un seul battement à la fois
        self._routine_en_cours = threading.Lock()
        self._battement_en_cours = threading.Lock()

        # signal de vie vers les deux cartes (garde-fou de perte de liaison)
        self._ping_stop = threading.Event()
        self.ping_period_s = 2

        # réglages tunables de la routine (pas de "bonne" valeur imposée par
        # le matériel : à ajuster à l'œil / à l'oreille sur place)
        self.heartbeat_every_s = 300            # battement toutes les 5 min de lecture
        self.heartbeat_duration_s = 35          # durée du battement (son + lumière)
        self.heartbeat_music_fade_s = 4         # descente / remontée de la musique autour du battement
        self.heartbeat_silence_after_s = 3      # noir et silence entre la fin du battement et la reprise
        self.lights_fade_out_ms = 6000          # descente des lumières vers le noir avant le battement
        # Forme du battement lumineux. Suivre directement la courbe ECG donnait
        # un clignotement : normalisée, elle est agitée en permanence (allumée
        # 97% du temps), sans repos entre les battements. Et un seul bond par
        # battement ne rendait pas le "boum-boum" caractéristique. On repère
        # donc chaque battement réel (un pic R par cycle cardiaque, détecté à
        # l'avance dans le fichier ECG) et on joue à chaque fois deux bonds
        # rapprochés (lub-dub), puis rien jusqu'au battement suivant.
        self.heartbeat_update_hz = 50
        self.heartbeat_bump_s = 0.18             # durée de chaque bond (lub ou dub)
        self.heartbeat_lub_dub_gap_s = 0.15     # silence entre le lub et le dub
        # entre les bonds (et au repos), la lumière ne redescend pas jusqu'au
        # noir complet : elle reste à ce niveau plancher (0-255), pour un
        # fondu plus doux (moins de contraste entre "rien" et le pic du bond)
        self.heartbeat_pwm_repos = 30
        self.heartbeat_pwm_pic = 90
        # comme un vrai cœur, le deuxième bond (dub) monte moins haut que le
        # premier (lub) : 1.0 = même hauteur, 0.5 = dub à mi-chemin entre le
        # repos et le pic du lub
        self.heartbeat_dub_ratio = 0.55
        # l'œil perçoit la luminosité de façon non linéaire : sans gamma, le
        # bond paraît sec en haut et écrasé en bas
        self.heartbeat_gamma = 2.2

        # Le son du cœur bat sur le même motif que la lumière : son calage
        # (écart lub-dub, sommet du boum au milieu du bond) vient d'ici, pour
        # que les deux restent synchrones si on retouche les bonds lumineux.
        # Le reste du son vient des réglages validés dans heartbeat_tuner.py.
        self.sonifier = HeartbeatSonifier(
            ecg_file,
            **_reglages_son_coeur(),
            lub_dub_s=self.heartbeat_bump_s + self.heartbeat_lub_dub_gap_s,
            lub_align_s=self.heartbeat_bump_s / 2,
        )
        # précalcule le rendu audio en tâche de fond dès le lancement, pour
        # que le tout premier battement de cœur n'ait pas de silence pendant
        # que _render() tourne (~13 s, mesuré sur INES_02.txt)
        threading.Thread(target=self.sonifier.preload, daemon=True).start()
        self.morse_start_delay_s = 10           # temps de musique seule avant que la lecture commence
        # chaque perceuse démarre à un instant tiré au hasard dans cette
        # fenêtre (en s après le début de la routine) : elles peuvent partir
        # ensemble ou décalées, sans ordre imposé
        self.perceuses_start_min_s = 10
        self.perceuses_start_max_s = 40
        # Chaque perceuse tourne ensuite en continu pour toute la durée de la
        # routine (voir _boucle_perceuse) : un cycle complet (rotation horaire
        # + antihoraire, même durée chacune) de durée aléatoire dans la plage
        # ci-dessous, puis un arrêt complet pendant une pause aléatoire entre
        # perceuses_pause_min_s et perceuses_pause_max_s, puis un nouveau
        # cycle — indéfiniment, sauf pendant un battement de cœur (rien ne
        # redémarre tant qu'il n'est pas terminé, le firmware l'a déjà mis en
        # pause à ce moment-là). Machines 2 et 3 ont un plancher plus haut que
        # la Machine 1 : leur rampe accel/décel de 5s par sens (ACCEL_MS/
        # DECEL_MS dans le firmware) refuse tout cycle complet sous 20s.
        self.perceuses_cycle_s = {
            1: (10, 40),
            2: (20, 40),
            3: (20, 40),
        }
        self.perceuses_pause_min_s = 30
        self.perceuses_pause_max_s = 240
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
                reply = self._sonder_identite(ser)
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

        if self.ser_lights or self.ser_motors:
            self._demarrer_signal_de_vie()
        return self.ser_lights is not None, self.ser_motors is not None

    @staticmethod
    def _sonder_identite(ser, essais=2, fenetre_s=2.0):
        """Envoie ID? et lit les lignes jusqu'à en trouver une qui ressemble à un
        identifiant AQBTCM, dans la limite de fenetre_s par essai.

        Une simple attente de 0.3s suivie d'un read() ratait la carte une fois
        sur trois : si la réponse n'était pas encore arrivée, read() ne ramenait
        qu'un seul octet ("A"), la carte était déclarée inconnue et le port
        refermé — ce qui la re-resettait au passage."""
        for _ in range(essais):
            ser.reset_input_buffer()
            ser.write(b"\nID?\n")  # le \n vide un éventuel octet parasite à l'ouverture du port
            fin = time.time() + fenetre_s
            while time.time() < fin:
                ligne = ser.readline().decode(errors="ignore").strip()
                if ID_LIGHTS in ligne or ID_MOTORS in ligne:
                    return ligne
        return ""

    def disconnect(self):
        self._ping_stop.set()
        for attr in ("ser_lights", "ser_motors"):
            ser = getattr(self, attr)
            if ser and ser.is_open:
                ser.close()
            setattr(self, attr, None)

    def _demarrer_signal_de_vie(self):
        """Envoie un PING régulier aux deux cartes. Chacune coupe tout d'elle-même
        si elle ne reçoit plus rien pendant PING_SILENCE_MAX_MS (voir les deux
        firmwares) : si le Pi meurt ou qu'un câble se débranche, les perceuses
        s'arrêtent et le fumigène est coupé sans intervention.

        PING est une commande silencieuse : aucune réponse, pour ne pas polluer
        le flux série que lit _attendre_ok."""
        self._ping_stop.clear()

        def _run():
            while not self._ping_stop.wait(self.ping_period_s):
                self._send_lights("PING")
                self._send_motors("PING")

        threading.Thread(target=_run, daemon=True).start()

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
                except serial.SerialException as e:
                    # englobe SerialTimeoutException : un câble débranché ou un
                    # ESP en reset ne doit jamais faire tomber l'appelant (la
                    # routine mourrait sans avoir arrêté perceuses et fumée)
                    print(f"[LIGHTS] envoi impossible ({e}): {cmd}")
        else:
            print(f"[LIGHTS] non connecté, commande perdue: {cmd}")

    def _send_motors(self, cmd):
        if self.ser_motors and self.ser_motors.is_open:
            with self._lock_motors:
                try:
                    self.ser_motors.write((cmd + "\n").encode())
                except serial.SerialException as e:
                    print(f"[MOTORS] envoi impossible ({e}): {cmd}")
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

        # La lecture ne doit JAMAIS s'arrêter d'elle-même : c'est la colonne
        # vertébrale de l'installation. Après quelques échecs de suite sur une
        # phrase on passe à la suivante (relire une phrase ou en sauter une est
        # sans conséquence), mais on ne sort de la boucle que sur stop_flag ou
        # à la fin du fichier.
        ECHECS_AVANT_DE_PASSER = 5
        i = 0
        echecs = 0
        while i < len(phrases):
            if self.stop_flag.is_set():
                print("Envoi phrases interrompu")
                return
            # un battement de cœur est en cours : on attend sa fin avant de (re)lire
            while self._heartbeat_active.is_set() and not self.stop_flag.is_set():
                time.sleep(0.1)

            try:
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
            except serial.SerialException as e:
                # liaison qui bronche : on attend et on réessaie, sans tuer le thread
                print(f"[LIGHTS] liaison perdue pendant la phrase {i + 1} ({e}), on réessaie.")
                self.stop_flag.wait(2)
                resultat = "timeout"

            if resultat == "ok":
                i += 1
                echecs = 0
            elif resultat == "interrompu":
                print("Lecture interrompue par le battement de cœur, la phrase sera relue.")
            elif resultat == "stop":
                print("Envoi phrases interrompu")
                return
            elif resultat == "erreur":
                print(f"L'ESP32 LIGHTS a refusé la phrase {i + 1}, on passe à la suivante.")
                i += 1
                echecs = 0
            else:
                # "redemarre" (l'ESP a rebooté en pleine phrase) ou "timeout"
                # (pas de OK : phrase abandonnée côté ESP, ou OK avalé)
                echecs += 1
                if echecs >= ECHECS_AVANT_DE_PASSER:
                    print(f"Phrase {i + 1} increvable après {echecs} essais, on passe à la suivante.")
                    i += 1
                    echecs = 0
                else:
                    raison = "a redémarré" if resultat == "redemarre" else "n'a pas répondu"
                    print(f"L'ESP32 LIGHTS {raison} sur la phrase {i + 1}, on la relit "
                          f"(essai {echecs}/{ECHECS_AVANT_DE_PASSER}).")
                    self.stop_flag.wait(1)  # laisse l'ESP finir son setup() avant de renvoyer

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

    def drill_set_cycle(self, drill_num, duree_s):
        """Fixe la durée de rotation d'une perceuse, la même dans les deux sens.
        Le firmware l'applique au prochain changement de sens, jamais au milieu
        d'une rotation. Evite de reflasher pour ajuster un rythme."""
        self._send_motors(f"D{drill_num}:CYCLE:{int(duree_s * 1000)}")

    def demarrer_perceuses_aleatoire(self):
        """Lance pour chaque perceuse une boucle en tâche de fond
        (_boucle_perceuse) : premier départ à un instant tiré au hasard dans
        la fenêtre [perceuses_start_min_s, perceuses_start_max_s] (elles
        peuvent partir ensemble ou décalées, sans ordre imposé), puis cycles
        et pauses aléatoires en continu jusqu'à la fin de la routine."""
        for drill_num in (1, 2, 3):
            delai = random.uniform(self.perceuses_start_min_s, self.perceuses_start_max_s)
            threading.Thread(
                target=self._boucle_perceuse,
                args=(drill_num, delai),
                daemon=True,
            ).start()

    def _boucle_perceuse(self, drill_num, delai_initial_s):
        """Fait tourner une perceuse en continu pour toute la durée de la
        routine : cycle complet (rotation horaire + antihoraire, même durée
        chacune) de durée aléatoire, arrêt complet, pause aléatoire, nouveau
        cycle... Rien ne redémarre pendant un battement de cœur — le firmware
        l'a déjà mis en pause à ce moment-là, le relancer par-dessus le
        court-circuiterait."""
        if self.stop_flag.wait(delai_initial_s):
            return  # arrêt demandé avant que cette perceuse ait démarré
        print(f"Perceuse {drill_num} démarre (t+{delai_initial_s:.0f}s)")
        while not self.stop_flag.is_set():
            while self._heartbeat_active.is_set() and not self.stop_flag.is_set():
                self.stop_flag.wait(0.1)
            if self.stop_flag.is_set():
                break

            cycle_min, cycle_max = self.perceuses_cycle_s[drill_num]
            duree_cycle = random.uniform(cycle_min, cycle_max)
            self.drill_set_cycle(drill_num, duree_cycle / 2)
            self.drill_start(drill_num)
            print(f"Perceuse {drill_num} : cycle de {duree_cycle:.0f}s")
            if self.stop_flag.wait(duree_cycle):
                break

            self.drill_stop(drill_num)
            pause = random.uniform(self.perceuses_pause_min_s, self.perceuses_pause_max_s)
            print(f"Perceuse {drill_num} : pause de {pause:.0f}s")
            if self.stop_flag.wait(pause):
                break

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

        # Chaque pulsation a SON propre signal d'arrêt. Avec un signal partagé,
        # un nouveau smoke_pulse() le rabaissait et ressuscitait l'ancien thread :
        # les deux s'entrelaçaient et un FUM_ON retardataire pouvait passer après
        # le FUM_OFF final, laissant le fumigène allumé sans surveillance.
        arret = threading.Event()

        def _run():
            n = 0
            while not arret.is_set() and not self.stop_flag.is_set():
                self._send_lights("FUM_ON")
                arret.wait(pulse_ms / 1000)
                self._send_lights("FUM_OFF")
                n += 1
                if repeats and n >= repeats:
                    break
                arret.wait(max(0, (period_ms - pulse_ms) / 1000))

        self.smoke_stop()  # coupe proprement une pulsation déjà en cours
        self._smoke_stop = arret
        self._smoke_thread = threading.Thread(target=_run, daemon=True)
        self._smoke_thread.start()

    def smoke_stop(self):
        self._smoke_stop.set()
        # on attend que le thread soit sorti AVANT le dernier FUM_OFF, pour que
        # OFF soit toujours la dernière commande envoyée au fumigène
        thread = self._smoke_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2)
        self._send_lights("FUM_OFF")

    # ==================== MUSIQUE ====================
    def init_music(self):
        if not mixer.get_init():
            # Tampon de 4096 échantillons (~93 ms). Le défaut de pygame 2 n'est
            # que de 512 (~12 ms) : trop juste sur le Pi, la moindre charge
            # (décodage MP3, threads de la routine, interface) le vide et la
            # musique saute. Pour une musique de fond, la latence est sans effet.
            mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)

    def music_start(self, volume=1.0):
        if not os.path.exists(self.music_file):
            print(f"Fichier audio manquant: {self.music_file}")
            return
        self.init_music()
        self.music_volume = volume
        mixer.music.load(self.music_file)
        mixer.music.set_volume(volume)
        # loops=-1 : la piste fait 9 min, sans bouclage l'installation jouait
        # dans le silence tout le reste de la journée. Le fichier commence et
        # finit sur du silence, donc le raccord est inaudible.
        mixer.music.play(loops=-1)
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
    def run_heartbeat_sequence(self, duration_s=None, update_hz=None):
        """Interruption battement de cœur :
        1. les perceuses s'arrêtent et les lumières s'éteignent (fin de la lecture morse)
        2. la musique descend jusqu'au silence
        3. le cœur bat, en son (HeartbeatSonifier) et en lumière, pendant duration_s
        4. tout s'éteint, un temps de noir et de silence
        5. les perceuses repartent, la musique remonte, et l'appelant reprend la lecture
        """
        duration_s = self.heartbeat_duration_s if duration_s is None else duration_s
        # un seul battement à la fois : deux en parallèle écrasent le flux audio
        # du sonifier, et le premier devient impossible à arrêter
        if not self._battement_en_cours.acquire(blocking=False):
            print("Un battement de cœur est déjà en cours.")
            return
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
                periode = 1 / (update_hz or self.heartbeat_update_hz)
                bump_s = self.heartbeat_bump_s
                gap_s = self.heartbeat_lub_dub_gap_s
                pwm_repos = self.heartbeat_pwm_repos
                pwm_pic_lub = self.heartbeat_pwm_pic
                pwm_pic_dub = pwm_repos + (self.heartbeat_pwm_pic - pwm_repos) * self.heartbeat_dub_ratio
                start = time.time()
                while time.time() - start < duration_s:
                    if self.stop_flag.is_set():
                        break
                    depuis = self.sonifier.get_time_since_last_beat()
                    bond = 0.0    # position dans le cosinus du bond en cours (0 = repos)
                    pwm_pic = pwm_pic_lub
                    if depuis is not None:
                        if depuis < bump_s:
                            bond = 0.5 * (1 - math.cos(2 * math.pi * depuis / bump_s))
                        else:
                            depuis -= bump_s + gap_s
                            if 0 <= depuis < bump_s:
                                bond = 0.5 * (1 - math.cos(2 * math.pi * depuis / bump_s))
                                pwm_pic = pwm_pic_dub
                    # gamma applique seulement a la forme de la montee (0-1),
                    # pas au plancher : celui-ci reste exactement pwm_repos au
                    # repos et pwm_pic au pic, quel que soit le gamma choisi
                    pwm = pwm_repos + (pwm_pic - pwm_repos) * bond ** self.heartbeat_gamma
                    self._send_lights(f"H:{int(pwm)}")
                    time.sleep(periode)
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
            self._battement_en_cours.release()
        print("Fin séquence battement de cœur")

    def run_heartbeat_sequence_thread(self, duration_s=None):
        threading.Thread(
            target=self.run_heartbeat_sequence, args=(duration_s,), daemon=True
        ).start()

    # ==================== ARRÊT D'URGENCE ====================
    def arret_urgence(self):
        print("⚠️ ARRÊT D'URGENCE ⚠️")
        self._verrouille = True   # rien ne redémarrera avant un rearmer() explicite
        self.stop_flag.set()
        # les parties mobiles d'abord, puis le fumigène : c'est ce qui compte
        # quand quelqu'un appuie sur le bouton rouge
        self.drills_stop_all()
        self.smoke_stop()
        self.all_lights_off()
        if mixer.get_init():
            mixer.music.stop()  # coupure instantanée voulue pour l'urgence, pas de fondu
        self.sonifier.stop(fade_ms=0)  # idem
        print("Tous les systèmes ont été mis hors tension.")

    def rearmer(self):
        """Lève le verrou posé par un arrêt d'urgence. Seul point d'entrée qui
        autorise à nouveau la routine et les tests à démarrer."""
        self._verrouille = False
        self.stop_flag.clear()
        print("Réarmé : la routine et les tests peuvent repartir.")

    @property
    def verrouille(self):
        return self._verrouille

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
        if self._verrouille:
            print("Arrêt d'urgence actif : réarmer avant de lancer la routine.")
            return
        # un seul déroulé à la fois : deux routines en parallèle donneraient deux
        # lecteurs morse sur le même port et deux battements dont l'un rend le
        # flux audio de l'autre injoignable (donc impossible à arrêter)
        if not self._routine_en_cours.acquire(blocking=False):
            print("Une routine tourne déjà.")
            return
        t_phrases = None
        try:
            self.stop_flag.clear()
            print("Routine lancée.")

            self.smoke_pulse(repeats=0)
            self.music_start(volume=1.0)
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
        finally:
            # quoi qu'il arrive — y compris sur une exception en pleine routine —
            # rien ne doit rester en marche sans surveillance
            self.smoke_stop()
            self.drills_stop_all()
            self.music_stop()
            # Les lumières aussi : l'ESP32 est autonome, quand on cesse de lui
            # envoyer des phrases il finit la sienne et le chœur continue de
            # réciter son mot en boucle, indéfiniment. On laisse d'abord le
            # thread morse sortir (il voit stop_flag en moins de 50 ms), sinon
            # il pourrait envoyer une dernière phrase après l'extinction.
            if t_phrases is not None:
                t_phrases.join(timeout=2)
            self.all_lights_off()
            self._routine_en_cours.release()
            print("Fin de routine.")

    def routine_thread(self):
        threading.Thread(target=self.routine, daemon=True).start()

    def interrompre_routine(self):
        self.stop_flag.set()
        self.music_stop()
        self.smoke_stop()
        self.all_lights_off()
        print("Signal d'interruption envoyé.")
