"""Test isolé des lumières + fumée (ESP32_LIGHTS uniquement).

Bench test : branche juste l'ESP32 lumières (à ton PC ou au Pi, peu importe),
pas besoin de l'ESP32 moteurs pour ce script.

Usage : python test_lights.py
"""

from aqbtcm_engine import Installation

HELP = """
--- Test lumières (ESP32_LIGHTS) ---
p <canal 0-15> <valeur 0-255>   : PWM manuel sur un canal
g <A|B|C> <valeur 0-255>        : PWM sur tout un groupe (4 tubes + ALL)
m <A|B|C> <phrase...> <mot>     : test morse (mot = mot du choeur, sans *)
h <valeur 0-255>                : mode heartbeat (même valeur sur A/B/C)
hstop                           : sort du mode heartbeat
f1 / f0                         : fumée ON / OFF
off                             : éteint toutes les lumières
?                                : ré-afficher cette aide
q                                : quitter (éteint tout avant de sortir)
"""


def main():
    install = Installation()
    print("Connexion...")
    lights_ok, motors_ok = install.connect()
    print(f"LIGHTS: {'OK' if lights_ok else 'ABSENT'} / MOTORS: {'OK' if motors_ok else 'absent (normal si non branché)'}")
    if not lights_ok:
        print("ESP32_LIGHTS introuvable : vérifie le câble USB et relance le script.")
        return
    print(HELP)

    try:
        while True:
            raw = input("> ").strip()
            if not raw:
                continue
            parts = raw.split()
            cmd = parts[0].lower()

            if cmd == "q":
                break
            elif cmd == "p" and len(parts) == 3:
                install.set_channel(int(parts[1]), int(parts[2]))
            elif cmd == "g" and len(parts) == 3:
                install.set_group(parts[1].upper(), int(parts[2]))
            elif cmd == "m" and len(parts) >= 4:
                soliste = parts[1].upper()
                mot = parts[-1]
                phrase = " ".join(parts[2:-1])
                install.raw_lights(f"M:{soliste}|{phrase}|*{mot}*")
            elif cmd == "h" and len(parts) == 2:
                install.raw_lights(f"H:{int(parts[1])}")
            elif cmd == "hstop":
                install.raw_lights("H:STOP")
            elif cmd == "f1":
                install.raw_lights("FUM_ON")
            elif cmd == "f0":
                install.raw_lights("FUM_OFF")
            elif cmd == "off":
                install.all_lights_off()
            elif cmd == "?":
                print(HELP)
            else:
                print(f"Commande inconnue: {raw!r}")
                print(HELP)
    finally:
        print("Extinction avant de quitter.")
        install.all_lights_off()
        install.raw_lights("FUM_OFF")
        install.disconnect()


if __name__ == "__main__":
    main()
