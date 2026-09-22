import serial
import time
import json

PORT = 'COM6'
BAUDRATE = 115200

def envoyer_commande(ser, phrase_soliste, mot_choeur):
    commande = {
        "mode": "soliste",
        "phrase": phrase_soliste,
        "choeur": mot_choeur
    }
    json_cmd = json.dumps(commande) + "\n"
    ser.write(json_cmd.encode())
    print(f"Envoyé : {json_cmd.strip()}")

def main():
    with serial.Serial(PORT, BAUDRATE, timeout=1) as ser:
        time.sleep(2)
        phrase = "Voici la phrase soliste."
        mot_choeur = "moto"
        envoyer_commande(ser, phrase, mot_choeur)
        time.sleep(15)  # Temps pour le test

if __name__ == "__main__":
    main()
