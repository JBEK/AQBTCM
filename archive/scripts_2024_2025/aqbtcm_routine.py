from pygame import mixer
from tkinter import *
from tkinter import filedialog
from nanpy import ArduinoApi, SerialManager
from time import sleep
import threading
import random

############################################################################
#########################    ARDUINO  SERIAL CONNEXIONS AN OUTPUT  ##################
############################################################################

try:
    slave_uno_drill = SerialManager(device='COM9')
    uno_drill = ArduinoApi(connection=slave_uno_drill)
    print("Arduino UNO DRILL connected")
except Exception as e:
    print(f"Failed to connect to Arduino UNO (Drill): {e}")

try:
    slave_mega_light = SerialManager(device='COM8')
    mega_light = ArduinoApi(connection=slave_mega_light)
    print("Arduino MEGA LIGHT A connected")
except Exception as e:
    print(f"Failed to connect to Arduino MEGA (Light A): {e}")

####OUTPUT
#NEON_LIGHT
neon_A_1 = 52
neon_A_2 = 50
neon_A_3 = 48
neon_A_4 = 46

neon_B_1 = 44
neon_B_2 = 42
neon_B_3 = 40
neon_B_4 = 38

neon_C_1 = 53
neon_C_2 = 51
neon_C_3 = 49
neon_C_4 = 47

neon_D_1 = 45
neon_D_2 = 43

neon_E_1 = 41
neon_E_2 = 30

mega_light.pinMode(neon_A_1, mega_light.OUTPUT)
mega_light.pinMode(neon_A_2, mega_light.OUTPUT)
mega_light.pinMode(neon_A_3, mega_light.OUTPUT)
mega_light.pinMode(neon_A_4, mega_light.OUTPUT)

mega_light.pinMode(neon_B_1, mega_light.OUTPUT)
mega_light.pinMode(neon_B_2, mega_light.OUTPUT)
mega_light.pinMode(neon_B_3, mega_light.OUTPUT)
mega_light.pinMode(neon_B_4, mega_light.OUTPUT)

mega_light.pinMode(neon_C_1, mega_light.OUTPUT)
mega_light.pinMode(neon_C_2, mega_light.OUTPUT)
mega_light.pinMode(neon_C_3, mega_light.OUTPUT)
mega_light.pinMode(neon_C_4, mega_light.OUTPUT)

# DRILLS
drill_1 = 3
drill_2 = 5
drill_3 = 9

# Morse code dictionary
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

def drill_on_and_off():
    print("Drills on")
    print("POWER = 200")
    sleep(0.5)
    uno_drill.analogWrite(drill_1, 200)
    uno_drill.analogWrite(drill_2, 200)
    uno_drill.analogWrite(drill_3, 200)
    sleep(4)
    print("MAX POWER")
    sleep(0.5)
    uno_drill.analogWrite(drill_1, 255)
    uno_drill.analogWrite(drill_2, 255)
    uno_drill.analogWrite(drill_3, 255)
    sleep(6)
    print("All OFF")
    sleep(4)
    uno_drill.analogWrite(drill_1, 0)
    uno_drill.analogWrite(drill_2, 0)
    uno_drill.analogWrite(drill_3, 0)

def music_start():
    mixer.init()
    mixer.music.load("echoic_chamber.mp3")
    mixer.music.set_volume(0.6)
    mixer.music.play()
    print("Starting music")

def music_stop():
    mixer.music.fadeout(3333)
    print("Music stopped")

def music_test():
    print("Testing music")
    sleep(1)
    music_start()
    sleep(5)
    music_stop()

def neons_A_on():
    print("Neon A all ON")
    mega_light.digitalWrite(neon_A_1, 0)
    mega_light.digitalWrite(neon_A_2, 0)
    mega_light.digitalWrite(neon_A_3, 0)
    mega_light.digitalWrite(neon_A_4, 0)

def neons_A_off():
    print("Neon A all OFF")
    mega_light.digitalWrite(neon_A_1, 1)
    mega_light.digitalWrite(neon_A_2, 1)
    mega_light.digitalWrite(neon_A_3, 1)
    mega_light.digitalWrite(neon_A_4, 1)

def all_neons_on():
    print("All neons ON")
    neons_A_on()
    # Add other groups (B, C, D) if necessary.

def all_neons_off():
    print("All neons OFF")
    neons_A_off()
    # Add other groups (B, C, D) if necessary.

def drill_test():
    print("Testing drills")
    print("Half power")
    sleep(0.5)
    uno_drill.analogWrite(drill_1, 125)
    uno_drill.analogWrite(drill_2, 125)
    uno_drill.analogWrite(drill_3, 125)
    sleep(2)
    print("Max power")
    sleep(0.5)
    uno_drill.analogWrite(drill_1, 255)
    uno_drill.analogWrite(drill_2, 255)
    uno_drill.analogWrite(drill_3, 255)
    sleep(2)
    print("All OFF")
    sleep(0.5)
    uno_drill.analogWrite(drill_1, 0)
    uno_drill.analogWrite(drill_2, 0)
    uno_drill.analogWrite(drill_3, 0)

def shutting_down_everything():
    try:
        uno_drill.close()
        print("Mega Drill disconnected")
    except:
        print("Couldn't disconnect Mega Drill")

    try:
        mega_light.close()
        print("Uno Light A disconnected")
    except:
        print("Couldn't disconnect Uno Light")

    try:
        mixer.music.stop()
        print("Music stopped")
    except:
        print("Couldn't stop Music")
