from pygame import mixer
from tkinter import *
from tkinter import filedialog
from nanpy import ArduinoApi, SerialManager
from time import sleep
import threading
from threading import Thread
import sys
import random







    ############################################################################
#########################    ARDUINO  SERIAL CONNEXIONS AN OUTPUT  ##################
    ############################################################################

#i=0
#ARDUINOS
 

try :
    slave_mega_light_1 = SerialManager(device='COM8')
    mega_light_1 = ArduinoApi(connection=slave_mega_light_1)
    print ("Arduino MEGA LIGHT 1 connected")
except:
    print ("Failed to connect to Arduino MEGA 1 (Light A+B)")

try :
    slave_mega_light_2 = SerialManager(device='COM8')
    mega_light_2 = ArduinoApi(connection=slave_mega_light_1)
    print ("Arduino MEGA LIGHT 2 connected")
except:
    print ("Failed to connect to Arduino MEGA 2 (Light B+C)")

try:
    slave_uno_drill = SerialManager(device='COM9') 
    uno_drill = ArduinoApi(connection=slave_uno_drill)
    print ("Arduino UNO DRILL connected")
except:
    print("Failed to connect to Arduino UNO DRILL (Light D + Drills 1+2+3)")


####OUTPUT

#########################NEON_LIGHT#####################################

#MEGA_LIGHT_1#
neon_A_1_WARM = 2
neon_A_1_COOL = 3
neon_A_2_WARM = 4
neon_A_2_COOL = 5
neon_A_3_WARM = 6
neon_A_3_COOL = 7
neon_A_4_WARM = 8
neon_A_4_COOL = 9

neon_B_1_WARM = 10
neon_B_1_COOL = 11
neon_B_2_WARM = 12
neon_B_2_COOL = 13
neon_B_3_WARM = 44
neon_B_3_COOL = 45
neon_B_4_WARM = 46
#MEGA_LIGHT_2#
neon_B_4_COOL =2

neon_C_1_WARM = 3
neon_C_1_COOL = 4
neon_C_2_WARM = 5
neon_C_2_COOL = 6 
neon_C_3_WARM = 7
neon_C_3_COOL = 8
neon_C_4_WARM = 9
neon_C_4_COOL = 10

# Initialisation des pins MEGA_LIGHT_1
for pin in [
    neon_A_1_WARM, neon_A_1_COOL,
    neon_A_2_WARM, neon_A_2_COOL,
    neon_A_3_WARM, neon_A_3_COOL,
    neon_A_4_WARM, neon_A_4_COOL,
    neon_B_1_WARM, neon_B_1_COOL,
    neon_B_2_WARM, neon_B_2_COOL,
    neon_B_3_WARM, neon_B_3_COOL,
    neon_B_4_WARM
]:
    slave_mega_light_1.pinMode(pin, slave_mega_light_1.OUTPUT)

# Initialisation des pins MEGA_LIGHT_2
for pin in [
    neon_B_4_COOL,
    neon_C_1_WARM, neon_C_1_COOL,
    neon_C_2_WARM, neon_C_2_COOL,
    neon_C_3_WARM, neon_C_3_COOL,
    neon_C_4_WARM, neon_C_4_COOL,
]:
    mega_light_2.pinMode(pin, mega_light_2.OUTPUT)



#################DRILLS####################################
drill_1 = 6
drill_2 = 9
drill_3 = 10

try:
    uno_drill.pinMode(drill_1, uno_drill.OUTPUT)
    uno_drill.pinMode(drill_2, uno_drill.OUTPUT)
    uno_drill.pinMode(drill_3, uno_drill.OUTPUT)

    print("UNO outputs (Light D4 + Drills) configured")
except:
    print("Failed to set UNO_drill outputs (Light D4 + Drills)")


morse_code = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--', 'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....',
    '6': '-....', '7': '--...', '8': '---..', '9': '----.'
}

    ############################################################################
##################################    FUNCTIONS DEF  #######################################
    ############################################################################



#######################################   DRILLS   ########################################################

def drill_on_and_off ():
    print ("Drills on")
    print ("POWER = 200")
    sleep(0.5)
    uno_drill.analogWrite(drill_1,200)
    uno_drill.analogWrite(drill_2,200)
    uno_drill.analogWrite(drill_3,200)
    sleep(4)
    print ("MAX POWER")
    sleep(0.5)
    uno_drill.analogWrite(drill_1,255)
    uno_drill.analogWrite(drill_2,255)
    uno_drill.analogWrite(drill_3,255)
    sleep(6)
    print ("All OFF")
    sleep(4)
    uno_drill.analogWrite(drill_1,0)
    uno_drill.analogWrite(drill_2,0)
    uno_drill.analogWrite(drill_3,0)

def old_fading_in_and_out(name,pin):
    intensity = 0
    fadeAmount = 5
   # print ("Drill_") + [__name__] +("fading")
    print ("Pin",pin, "is fading in and out")
    for i in range (103):
    # set the brightness of pin 9:
        name.analogWrite(pin, intensity)
    # change the brightness for next time through the loop:
        intensity += fadeAmount
    # reverse the direction of the fading at the ends of the fade: 
        if intensity == 0 or intensity == 255:
            fadeAmount = -fadeAmount         
    # wait for 30 milliseconds to see the dimming effect 
        sleep (0.03)

def old_fading_to_max(name,pin):
    intensity = 0
    fadeAmount = 5
   # print ("Drill_") + [__name__] +("fading")
    print ("Pin",pin, "is fading to max")
    for i in range (80):
    # set the brightness of pin 9:
        name.analogWrite(pin, intensity)
    # change the brightness for next time through the loop:
        intensity += fadeAmount
    # reverse the direction of the fading at the ends of the fade: 
        if intensity == 0 or intensity == 255:
            fadeAmount = fadeAmount


#from chatGPT
def fade_in(drill,maxvalue):
    for i in range(0, maxvalue):
        uno_drill.analogWrite(drill, i)
        sleep(3)  # Délai pour observer l'effet de fading

    for i in range(maxvalue, -1, -1):
        uno_drill.analogWrite(drill, i)
        sleep(3)  # Délai pour observer l'effet de fading
    i = i+1

def fade_in_and_out(drill,maxvalue):
    for i in range(0, maxvalue):
        uno_drill.analogWrite(drill, i)
        sleep(0.01)  # Délai pour observer l'effet de fading

    for i in range(maxvalue, -1, -1):
        uno_drill.analogWrite(drill, i)
        sleep(0.01)  # Délai pour observer l'effet de fading
  

#STOP DRILLS
def stopdrill_1():
    uno_drill.analogWrite(drill_1, 0)
    print("drill_1 OFF")

def stopDrill_2():
    uno_drill.analogWrite(drill_2,0)
    print("Drill_2 OFF")

def stopDrill_3():
    uno_drill.analogWrite(drill_3,0)
    print("Drill_3 OFF")


#####################################    MUSIC    ##################################################
# START AND FADING OUT MUSIC
def music_start():
    mixer.init()
    mixer.music.load("echoic_chamber.mp3")
    mixer.music.set_volume(0.6)
    mixer.music.play()
    print ("Starting music")

def music_stop():
    mixer.music.fadeout(3333)
    print ("Music stopped")

def music_test():
    print ("Testing music")
    sleep (1)
    music_start()
    sleep (5)
    music_stop()
#################################### NEON LIGHTS ###############################################

# Liste des pins pour les néons A WARM
neon_A_WARM_pins = [neon_A_1_WARM, neon_A_2_WARM, neon_A_3_WARM, neon_A_4_WARM]

def set_neons_A_WARM(state):
    action = 255 if state else 0  # Si `state` est True, allume à 255 (ON), sinon éteint (0)
    for pin in neon_A_WARM_pins:
        mega_light_1.analogWrite(pin, action)
    print(f"Neon A WARM all {'ON' if state else 'OFF'}")

# Usage pour allumer ou éteindre
set_neons_A_WARM(True)  # Allume tous les néons A WARM
set_neons_A_WARM(False)  # Éteint tous les néons A WARM


# Liste des pins pour les néons A COOL
neon_A_COOL_pins = [neon_A_1_COOL, neon_A_2_COOL, neon_A_3_COOL, neon_A_4_COOL]

def set_neons_A_COOL(state):
    action = 255 if state else 0  # Si `state` est True, allume à 255 (ON), sinon éteint (0)
    for pin in neon_A_COOL_pins:
        mega_light_1.analogWrite(pin, action)
    print(f"Neon A COOL all {'ON' if state else 'OFF'}")

# Usage pour allumer ou éteindre
set_neons_A_COOL(True)  # Allume tous les néons A COOL
set_neons_A_COOL(False)  # Éteint tous les néons A COOL



# Liste des pins pour les néons B WARM
neon_B_WARM_pins = [neon_B_1_WARM, neon_B_2_WARM, neon_B_3_WARM, neon_B_4_WARM]

def set_neons_B_WARM(state):
    action = 255 if state else 0  # Si `state` est True, allume à 255 (ON), sinon éteint (0)
    for pin in neon_B_WARM_pins:
        mega_light_1.analogWrite(pin, action)
    print(f"Neon B WARM all {'ON' if state else 'OFF'}")

# Usage pour allumer ou éteindre
set_neons_B_WARM(True)  # Allume tous les néons B WARM
set_neons_B_WARM(False)  # Éteint tous les néons B WARM


# Liste des pins pour les néons B COOL
neon_B_COOL_pins = [neon_B_1_COOL, neon_B_2_COOL, neon_B_3_COOL, neon_B_4_COOL]

def set_neons_B_COOL(state):
    action = 255 if state else 0  # Si `state` est True, allume à 255 (ON), sinon éteint (0)
    
    # On passe par tous les pins sauf le dernier
    for pin in neon_B_COOL_pins[:-1]:  # Tous sauf le dernier
        mega_light_1.analogWrite(pin, action)
        
    # Le dernier pin est sur mega_light_2, donc on l'écrit séparément
    mega_light_2.analogWrite(neon_B_4_COOL, action)
    
    print(f"Neon B COOL all {'ON' if state else 'OFF'}")

# Usage pour allumer ou éteindre
set_neons_B_COOL(True)  # Allume tous les néons B COOL
set_neons_B_COOL(False)  # Éteint tous les néons B COOL


# Liste des pins pour les néons C WARM
neon_C_WARM_pins = [neon_C_1_WARM, neon_C_2_WARM, neon_C_3_WARM, neon_C_4_WARM]

def set_neons_C_WARM(state):
    action = 255 if state else 0  # Si `state` est True, allume à 255 (ON), sinon éteint (0)
    for pin in neon_C_WARM_pins:
        mega_light_2.analogWrite(pin, action)
    print(f"Neon C WARM all {'ON' if state else 'OFF'}")

# Usage pour allumer ou éteindre
set_neons_C_WARM(True)  # Allume tous les néons C WARM
set_neons_C_WARM(False)  # Éteint tous les néons C WARM


# Liste des pins pour les néons C COOL
neon_C_COOL_pins = [neon_C_1_COOL, neon_C_2_COOL, neon_C_3_COOL, neon_C_4_COOL]

def set_neons_C_COOL(state):
    action = 255 if state else 0  # Si `state` est True, allume à 255 (ON), sinon éteint (0)
    for pin in neon_C_COOL_pins:
        mega_light_2.analogWrite(pin, action)
    print(f"Neon C COOL all {'ON' if state else 'OFF'}")

# Usage pour allumer ou éteindre
set_neons_C_COOL(True)  # Allume tous les néons C COOL
set_neons_C_COOL(False)  # Éteint tous les néons C COOL

 

def all_neons_WARM_on():
    print ("All neons WARM ON")
    set_neons_A_WARM(True)
    set_neons_B_WARM(True)
    set_neons_C_WARM(True)

def all_neons_WARM_off():
    print ("All neons WARM OFF")
    set_neons_A_WARM(False)
    set_neons_B_WARM(False)
    set_neons_C_WARM(False)

def all_neons_COOL_on():
    print ("All neons COLD ON")
    set_neons_A_COOL(True)
    set_neons_B_COOL(True)
    set_neons_C_COOL(True)

def all_neons_COOL_off():
    print ("All neons COLD OFF")
    set_neons_A_COOL(False)
    set_neons_B_COOL(False)
    set_neons_C_COOL(False)

def all_neons_on ():
    print ("All neons  ON")
    all_neons_WARM_on()
    all_neons_COOL_on()

def all_neons_off ():
    print ("All neons  OFF")
    all_neons_WARM_off()
    all_neons_COOL_off()


def rohlala ():
    print("Rohlala is running")

    # Séquence d'allumage des néons (en séquence avec un délai de 0.08s)

    # Néo A (MEGA_LIGHT_1)
    mega_light_1.digitalWrite(neon_A_1_WARM, 1)  # Allume le néon A 1 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_B_1_WARM, 1)  # Allume le néon B 1 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_C_1_WARM, 1)  # Allume le néon C 1 WARM
    sleep(0.08)

    mega_light_1.digitalWrite(neon_A_2_WARM, 1)  # Allume le néon A 2 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_B_2_WARM, 1)  # Allume le néon B 2 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_C_2_WARM, 1)  # Allume le néon C 2 WARM
    sleep(0.08)

    mega_light_1.digitalWrite(neon_A_3_WARM, 1)  # Allume le néon A 3 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_B_3_WARM, 1)  # Allume le néon B 3 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_C_3_WARM, 1)  # Allume le néon C 3 WARM
    sleep(0.08)

    mega_light_1.digitalWrite(neon_A_4_WARM, 1)  # Allume le néon A 4 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_B_4_WARM, 1)  # Allume le néon B 4 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_C_4_WARM, 1)  # Allume le néon C 4 WARM
    sleep(0.08)

    # Séquence d'extinction des néons (en séquence inverse avec un délai de 0.08s)
    
    # Extinction Néo A, B, C (MEGA_LIGHT_1)
    mega_light_1.digitalWrite(neon_A_4_WARM, 0)  # Éteint le néon A 4 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_B_4_WARM, 0)  # Éteint le néon B 4 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_C_4_WARM, 0)  # Éteint le néon C 4 WARM
    sleep(0.08)

    mega_light_1.digitalWrite(neon_A_3_WARM, 0)  # Éteint le néon A 3 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_B_3_WARM, 0)  # Éteint le néon B 3 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_C_3_WARM, 0)  # Éteint le néon C 3 WARM
    sleep(0.08)

    mega_light_1.digitalWrite(neon_A_2_WARM, 0)  # Éteint le néon A 2 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_B_2_WARM, 0)  # Éteint le néon B 2 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_C_2_WARM, 0)  # Éteint le néon C 2 WARM
    sleep(0.08)

    mega_light_1.digitalWrite(neon_A_1_WARM, 0)  # Éteint le néon A 1 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_B_1_WARM, 0)  # Éteint le néon B 1 WARM
    sleep(0.08)
    mega_light_1.digitalWrite(neon_C_1_WARM, 0)  # Éteint le néon C 1 WARM
    sleep(0.08)



def random_on_off_warm():
    print("Random On/Off WARM is running")
    all_neons_COOL_off()

    # Liste de tous les néons WARM (les cold resteront éteints)
    neons_warm = [
        (mega_light_1, neon_A_1_WARM), (mega_light_1, neon_B_1_WARM), (mega_light_1, neon_C_1_WARM),
        (mega_light_1, neon_A_2_WARM), (mega_light_1, neon_B_2_WARM), (mega_light_1, neon_C_2_WARM),
        (mega_light_1, neon_A_3_WARM), (mega_light_1, neon_B_3_WARM), (mega_light_1, neon_C_3_WARM),
        (mega_light_1, neon_A_4_WARM), (mega_light_1, neon_B_4_WARM), (mega_light_1, neon_C_4_WARM)
    ]
    
    # Pour chaque néon dans la liste des WARM, choisir aléatoirement d'allumer ou d'éteindre
    for controller, neon in neons_warm:
        state = random.choice([0, 1])  # Choisir aléatoirement 0 (éteint) ou 1 (allumé)
        controller.digitalWrite(neon, state)
        sleep(0.08)  # Ajouter un petit délai entre chaque action pour éviter une exécution trop rapide

    print("Random On/Off WARM sequence completed.")

# Dictionnaire de correspondance Morse


def send_morse(char):
    if char == '.':
        mega_light.digitalWrite(neon_A_1, mega_light.HIGH)  # Allume la LED pour un point
        sleep(0.1)  # Durée d'un point en secondes (ajustez selon vos besoins)
        mega_light.digitalWrite(neon_A_1, mega_light.LOW)  # Éteint la LED
        sleep(0.1)  # Attendez un court instant entre les signaux morse
    elif char == '-':
        mega_light.digitalWrite(neon_A_1, mega_light.HIGH)  # Allume la LED pour un tiret
        sleep(0.3)  # Durée d'un tiret en secondes (ajustez selon vos besoins)
        mega_light.digitalWrite(neon_A_1, mega_light.LOW)  # Éteint la LED
        sleep(0.1)  # Attendez un court instant entre les signaux morse
    elif char == ' ':
        sleep(0.2)  # Attendez un court instant entre les lettres en secondes (ajustez selon vos besoins)

def text_to_morse(text):
    morse_message = ''
    for char in text:
        if char == ' ':
            morse_message += ' '  # Ajoute un espace entre les mots
        else:
            char = char.upper()
            if char in morse_code:
                morse_message += morse_code[char] + ' '  # Ajoute la lettre en morse

    return morse_message

def writing_morse():
# Texte que vous souhaitez traduire en morse
    text_to_translate = "Ainsi parlerent les eloquentes filles du grand Jupiter, et elles me remirent pour sceptre un rameau de vert laurier superbe à cueillir puis, minspirant un divin langage pour me faire chanter le passe etlavenir, elles mordonnèrent de celebrer lorigine des bienheureux Immortels et de les choisir toujours elles memes pour objet de mes premiers et de mes derniers chants. Mais pourquoi marrêter ainsi autour du chêne ou du rocher  "
    morse_message = text_to_morse(text_to_translate)

# Envoi des signaux lumineux en morse à l'Arduino
    for char in morse_message:
        if char == ' ':
            sleep(0.2)  # Attendez un court instant entre les mots en secondes (ajustez selon vos besoins)
        else:
            send_morse(char)

# Fermez la connexion série
    mega_light_1.close()


def both_drill_and_lights ():
    rohlala()
    drill_on_and_off()

        ################################################################
##################################    TESTS   #######################################
        ################################################################

def light_test ():
    print ("Starting lightening test")
    sleep (1)
    all_neons_off()
    sleep(2)

    print ("Testing neons A WARM")
    sleep (1)
    set_neons_A_WARM(True)
    sleep (2)
    set_neons_A_WARM(False)
    sleep (1)
    print ("Testing neons A COOL")
    sleep (1)
    set_neons_A_COOL(True)
    sleep (2)
    set_neons_A_COOL(False)
    sleep (2)

    print ("Testing neons B WARM")
    sleep (1)
    set_neons_B_WARM(True)
    sleep (2)
    set_neons_B_WARM(False)
    sleep (1)
    print ("Testing neons B COOL")
    sleep (1)
    set_neons_B_COOL(True)
    sleep (2)
    set_neons_B_COOL(False)
    sleep (2)

    print ("Testing neons C WARM")
    sleep (1)
    set_neons_C_WARM(True)
    sleep (2)
    set_neons_C_WARM(False)
    sleep (1)
    print ("Testing neons C COOL")
    sleep (1)
    set_neons_C_COOL(True)
    sleep (2)
    set_neons_C_COOL(False)
    sleep (2)


    print ("Testing all neons together")
    sleep (1)
    all_neons_off()
    sleep (2)
    all_neons_on()
    sleep(3)
    all_neons_off()
    print ("Light test over")
    
def current_test ():
    drill_on_and_off ()
    sleep (4)

def drill_test ():
    print ("Testing drills")
    print ("Half power")
    sleep(0.5)
    uno_drill.analogWrite(drill_1,125)
    uno_drill.analogWrite(drill_2,125)
    uno_drill.analogWrite(drill_3,125)
    sleep(2)
    print ("Max power")
    sleep(0.5)
    uno_drill.analogWrite(drill_1,255)
    uno_drill.analogWrite(drill_2,255)
    uno_drill.analogWrite(drill_3,255)
    sleep(2)
    print ("All OFF")
    sleep(0.5)
    uno_drill.analogWrite(drill_1,0)
    uno_drill.analogWrite(drill_2,0)
    uno_drill.analogWrite(drill_3,0)
    
def shutting_down_everything () :
    try :
        uno_drill.close()
        print ("Mega Drill disconnected")
    except :
        print ("Couldn't disconnect Mega Drill")

    try :
        mega_light_1.close()
        print ("Uno Light A+B disconnected")
    except :
        print ("Couldn't disconnect Uno Light")

    try :
        mega_light_2.close()
        print ("Uno Light B+C disconnected")
    except :
        print ("Couldn't disconnect Uno Light")

    try :
        mixer.music.stop()
        print ("Music stopped")
    except :
        print ("Couldn't stop Music")

'''
stop = False

def button_stop_command():
    # If the STOP button is pressed then terminate the loop
    global stop
    stop = True


def button_start_command():
  global stop
  stop = False
  while True and not stop:
    routine()

def button_starter():
  t = threading.Thread(target=button_start_command)
  t.start()



def start_loop():
    # Fonction contenant la boucle que vous souhaitez exécuter en continu
    # Remplacez ce bloc par votre propre code de boucle
    routine ()
    global running
    running = True
    while running:
        # Votre code ici...
        window.update()  # Mettre à jour la fenêtre (utile si votre boucle utilise Tkinter)

        # Délai en millisecondes pour la boucle avant de la relancer
        window.after(1000)  # La boucle s'exécute toutes les 1000 ms (1 seconde)

def stop_loop():
    # Fonction pour arrêter la boucle
    global running
    running = False

running = False
'''


 








#########################################################################
############################### PROGRAM #################################
#########################################################################

def routine():
   # fade_in(drill_1,255)
    all_neons_off ()
    sleep (3)
    music_start()
    sleep(3)
    all_neons_on()
    sleep (2)
    all_neons_off()
    sleep (4)
    random_on_off_warm()
    sleep (4)
    all_neons_off()
    sleep(5)
    for i in range (3):
     rohlala()
    sleep (4)
    for i in range (1):
        random_on_off_warm()
    sleep (4)

    all_neons_off()

    sleep (3)
                            
    '''
    fading_to_max (uno_drill,drill_3)
    sleep (1)

    fading_in_and_out(uno_drill,drill_1)
    fading_in_and_out(uno_drill,drill_2)
    fading_in_and_out(uno_drill,drill_3)
    sleep (2)

    for i in range (3) :                #STARTING FIRST DRILL
        first_drill_prog()
    sleep (1)

    for i in range (5):
        false_random_neon()

    tralalou()
    all_neons_off()
    sleep (4)
'''

# STOP MUSIC
    music_stop()
    sleep (1)

#STOP DRILLS
    stopdrill_1()
    sleep (1)
    stopDrill_2 ()
    sleep (2)



############################################################################
##################################  TKINTER  ###############################
############################################################################
def fonction_open():
    filedialog.askopenfilename()
    
window = Tk ()
window.title("AQBTCM PROGRAM")
window.geometry("720x480")
window.config(background='white')

frame=Frame(window, bg='white')
# interface = Interface(fenetre)
champ_label = Label(frame, text= "Hello dear \n What do you want to do ? \n")
champ_label.pack()


start_button = Button(frame, text="Start", command=routine)
start_button.pack(pady=10, fill=X)

pause_button = Button(frame, text="Pause", command=stop_loop)
pause_button.pack(pady=10, fill=X)

stop_button = Button(frame, text="Stop", command=stop_loop)
stop_button.pack(pady=10, fill=X)

current_test_button = Button(frame, text="Current Test", command=current_test)
current_test_button.pack(pady=10, fill=X)


music_test_button = Button(frame, text="Music Test", command=music_test)
music_test_button.pack(pady=10, fill=X)

light_test_button = Button(frame, text="Light Test", command=light_test)
light_test_button.pack(pady=10, fill=X)

drill_test_button = Button(frame, text="Drill Test", command=drill_test)
drill_test_button.pack(pady=10, fill=X)

shutdown_button = Button(frame, text="SHUTDOWN",background='red', command=shutting_down_everything)
shutdown_button.pack(pady=10, fill=X)

quit_button = Button(frame, text="Quit", command=window.quit)
quit_button.pack(pady=10, fill=X)


frame.pack (expand=YES)

window.mainloop()
sleep(1)


