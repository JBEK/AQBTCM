from nanpy import ArduinoApi
from nanpy import SerialManager
import time

# Configuration de la connexion avec Arduino
connection = SerialManager(device='COM8')  # Remplacez par le port série approprié pour votre Arduino
a = ArduinoApi(connection=connection)

# Définir le numéro de broche connecté à la LED
led_pin = 9

# Définir la broche comme sortie
a.pinMode(led_pin, a.OUTPUT)

# Fonction pour effectuer l'effet de fading sur la LED
def fade_led():
    for i in range(0, 256):
        a.analogWrite(led_pin, i)
        time.sleep(0.01)  # Délai pour observer l'effet de fading

# Appel de la fonction pour réaliser l'effet de fading
fade_led()