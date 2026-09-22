"""Test isolé des perceuses (ESP32_MOTORS uniquement).

Bench test : branche juste l'ESP32 moteurs (à ton PC ou au Pi, peu importe),
pas besoin de l'ESP32 lumières pour ce script.

Usage : python test_perceuses.py
"""

import time

from aqbtcm_engine import Installation

HELP = """
--- Test perceuses (ESP32_MOTORS) ---
1 / 2 / 3   : démarrer la perceuse 1 / 2 / 3
0           : démarrer les 3 (D:ALL:START)
s1 s2 s3    : arrêter la perceuse 1 / 2 / 3
sa          : arrêter les 3 (D:ALL:STOP)
h           : test pause/reprise (H:START, 5s, puis H:STOP) sur ce qui tourne
?           : ré-afficher cette aide
q           : quitter (arrête tout avant de sortir)
"""


def main():
    install = Installation()
    print("Connexion...")
    lights_ok, motors_ok = install.connect()
    print(f"MOTORS: {'OK' if motors_ok else 'ABSENT'} / LIGHTS: {'OK' if lights_ok else 'absent (normal si non branché)'}")
    if not motors_ok:
        print("ESP32_MOTORS introuvable : vérifie le câble USB et relance le script.")
        return
    print(HELP)

    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == "q":
                break
            elif cmd in ("1", "2", "3"):
                install.drill_start(int(cmd))
            elif cmd == "0":
                install.drills_start_all()
            elif cmd in ("s1", "s2", "s3"):
                install.drill_stop(int(cmd[1]))
            elif cmd == "sa":
                install.drills_stop_all()
            elif cmd == "h":
                print("H:START (pause 5s)...")
                install.raw_motors("H:START")
                time.sleep(5)
                print("H:STOP (reprise)...")
                install.raw_motors("H:STOP")
            elif cmd in ("", "?"):
                print(HELP)
            else:
                print(f"Commande inconnue: {cmd!r}")
                print(HELP)
    finally:
        print("Arrêt de tous les moteurs avant de quitter.")
        install.drills_stop_all()
        install.disconnect()


if __name__ == "__main__":
    main()
