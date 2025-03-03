from pygame import mixer
from tkinter import *
from tkinter import filedialog
import threading
from time import sleep
import random

############################################################################
#########################    ARDUINO  SERIAL CONNEXIONS AN OUTPUT  ##################
############################################################################

uno_light = None
mega_drill = None

try:
    from nanpy import ArduinoApi, SerialManager
    slave_mega_drill = SerialManager(device='COM9') 
    mega_drill = ArduinoApi(connection=slave_mega_drill)
    print("Arduino MEGA DRILL connected")
except:
    print("Failed to connect to Arduino MEGA (Drill)")

try:
    slave_uno_light = SerialManager(device='COM8')
    uno_light = ArduinoApi(connection=slave_uno_light)
    print("Arduino UNO LIGHT A connected")
except:
    print("Failed to connect to Arduino UNO (Light A)")


####OUTPUT

# NEON_LIGHT
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

if uno_light:
    uno_light.pinMode(neon_A_1, uno_light.OUTPUT)
    uno_light.pinMode(neon_A_2, uno_light.OUTPUT)
    uno_light.pinMode(neon_A_3, uno_light.OUTPUT)
    uno_light.pinMode(neon_A_4, uno_light.OUTPUT)

    uno_light.pinMode(neon_B_1, uno_light.OUTPUT)
    uno_light.pinMode(neon_B_2, uno_light.OUTPUT)
    uno_light.pinMode(neon_B_3, uno_light.OUTPUT)
    uno_light.pinMode(neon_B_4, uno_light.OUTPUT)

    uno_light.pinMode(neon_C_1, uno_light.OUTPUT)
    uno_light.pinMode(neon_C_2, uno_light.OUTPUT)
    uno_light.pinMode(neon_C_3, uno_light.OUTPUT)
    uno_light.pinMode(neon_C_4, uno_light.OUTPUT)

# DRILLS
drill_1 = 3
drill_2 = 5
drill_3 = 9

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

def drill_on_and_off():
    if not mega_drill:
        print("Simulating drills on and off")
        return

    print("Drills on")
    print("POWER = 200")
    sleep(0.5)
    mega_drill.analogWrite(drill_1, 200)
    mega_drill.analogWrite(drill_2, 200)
    mega_drill.analogWrite(drill_3, 200)
    sleep(4)
    print("MAX POWER")
    sleep(0.5)
    mega_drill.analogWrite(drill_1, 255)
    mega_drill.analogWrite(drill_2, 255)
    mega_drill.analogWrite(drill_3, 255)
    sleep(6)
    print("All OFF")
    sleep(4)
    mega_drill.analogWrite(drill_1, 0)
    mega_drill.analogWrite(drill_2, 0)
    mega_drill.analogWrite(drill_3, 0)

def old_fading_in_and_out(name, pin):
    if not mega_drill:
        print(f"Simulating fading in and out on pin {pin}")
        return

    intensity = 0
    fadeAmount = 5
    print("Pin", pin, "is fading in and out")
    for i in range(103):
        name.analogWrite(pin, intensity)
        intensity += fadeAmount
        if intensity == 0 or intensity == 255:
            fadeAmount = -fadeAmount
        sleep(0.03)

def old_fading_to_max(name, pin):
    if not mega_drill:
        print(f"Simulating fading to max on pin {pin}")
        return

    intensity = 0
    fadeAmount = 5
    print("Pin", pin, "is fading to max")
    for i in range(80):
        name.analogWrite(pin, intensity)
        intensity += fadeAmount
        if intensity == 0 or intensity == 255:
            fadeAmount = fadeAmount

def fade_in(drill, maxvalue):
    if not mega_drill:
        print(f"Simulating fade in on drill {drill} to {maxvalue}")
        return

    for i in range(0, maxvalue):
        mega_drill.analogWrite(drill, i)
        sleep(0.03)

    for i in range(maxvalue, -1, -1):
        mega_drill.analogWrite(drill, i)
        sleep(0.03)

def fade_in_and_out(drill, maxvalue):
    if not mega_drill:
        print(f"Simulating fade in and out on drill {drill} to {maxvalue}")
        return

    for i in range(0, maxvalue):
        mega_drill.analogWrite(drill, i)
        sleep(0.01)

    for i in range(maxvalue, -1, -1):
        mega_drill.analogWrite(drill, i)
        sleep(0.01)

def stop_drill_1():
    if not mega_drill:
        print("Simulating drill_1 OFF")
        return

    mega_drill.analogWrite(drill_1, 0)
    print("drill_1 OFF")

def stop_drill_2():
    if not mega_drill:
        print("Simulating drill_2 OFF")
        return

    mega_drill.analogWrite(drill_2, 0)
    print("drill_2 OFF")

def stop_drill_3():
    if not mega_drill:
        print("Simulating drill_3 OFF")
        return

    mega_drill.analogWrite(drill_3, 0)
    print("drill_3 OFF")

#####################################    MUSIC    ##################################################
def music_start():
    mixer.init()
    mixer.music.load("C:\\Users\\jeann\\Documents\\PROJECTS\\AQBTCM\\AQBTCM_RASPUINO\\all_new_aqbtcm.mp3")
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

#################################### NEON LIGHTS ###############################################

def neons_A_on():
    if not uno_light:
        print("Simulating Neon A all ON")
        return

    print("Neon A all ON")
    uno_light.digitalWrite(neon_A_1, 0)
    uno_light.digitalWrite(neon_A_2, 0)
    uno_light.digitalWrite(neon_A_3, 0)
    uno_light.digitalWrite(neon_A_4, 0)

def neons_A_off():
    if not uno_light:
        print("Simulating Neon A all OFF")
        return

    print("Neon A all OFF")
    uno_light.digitalWrite(neon_A_1, 1)
    uno_light.digitalWrite(neon_A_2, 1)
    uno_light.digitalWrite(neon_A_3, 1)
    uno_light.digitalWrite(neon_A_4, 1)

def neons_B_on():
    if not uno_light:
        print("Simulating Neon B all ON")
        return

    print("Neons B all ON")
    uno_light.digitalWrite(neon_B_1, 0)
    uno_light.digitalWrite(neon_B_2, 0)
    uno_light.digitalWrite(neon_B_3, 0)
    uno_light.digitalWrite(neon_B_4, 0)

def neons_B_off():
    if not uno_light:
        print("Simulating Neon B all OFF")
        return

    print("Neons B all OFF")
    uno_light.digitalWrite(neon_B_1, 1)
    uno_light.digitalWrite(neon_B_2, 1)
    uno_light.digitalWrite(neon_B_3, 1)
    uno_light.digitalWrite(neon_B_4, 1)

def neons_C_on():
    if not uno_light:
        print("Simulating Neon C all ON")
        return

    print("Neons C all ON")
    uno_light.digitalWrite(neon_C_1, 0)
    uno_light.digitalWrite(neon_C_2, 0)
    uno_light.digitalWrite(neon_C_3, 0)
    uno_light.digitalWrite(neon_C_4, 0)

def neons_C_off():
    if not uno_light:
        print("Simulating Neon C all OFF")
        return

    print("Neons C all OFF")
    uno_light.digitalWrite(neon_C_1, 1)
    uno_light.digitalWrite(neon_C_2, 1)
    uno_light.digitalWrite(neon_C_3, 1)
    uno_light.digitalWrite(neon_C_4, 1)

def neons_D_on():
    if not uno_light:
        print("Simulating Neon D all ON")
        return

    print("Neons D all ON")
    uno_light.digitalWrite(neon_D_1, 0)
    uno_light.digitalWrite(neon_D_2, 0)

def neons_D_off():
    if not uno_light:
        print("Simulating Neon D all OFF")
        return

    print("Neons D all OFF")
    uno_light.digitalWrite(neon_D_1, 1)
    uno_light.digitalWrite(neon_D_2, 1)

def neons_E_on():
    if not uno_light:
        print("Simulating Neon E all ON")
        return

    print("Neons E all ON")
    uno_light.digitalWrite(neon_E_1, 0)
    uno_light.digitalWrite(neon_E_2, 0)

def neons_E_off():
    if not uno_light:
        print("Simulating Neon E all OFF")
        return

    print("Neons E all OFF")
    uno_light.digitalWrite(neon_E_1, 1)
    uno_light.digitalWrite(neon_E_2, 1)

def neons_all_on():
    if not uno_light:
        print("Simulating all neons ON")
        return

    print("All neons ON")
    neons_A_on()
    sleep(1)
    neons_B_on()
    sleep(1)
    neons_C_on()
    sleep(1)
    neons_D_on()
    sleep(1)
    neons_E_on()
    sleep(1)

def neons_all_off():
    if not uno_light:
        print("Simulating all neons OFF")
        return

    print("All neons OFF")
    neons_A_off()
    sleep(1)
    neons_B_off()
    sleep(1)
    neons_C_off()
    sleep(1)
    neons_D_off()
    sleep(1)
    neons_E_off()
    sleep(1)

def morse_char(pin, char):
    if not uno_light:
        print(f"Simulating Morse code '{char}' on pin {pin}")
        return

    for symbol in morse_code[char]:
        if symbol == '-':
            uno_light.digitalWrite(pin, 0)
            sleep(0.3)
            uno_light.digitalWrite(pin, 1)
            sleep(0.1)
        elif symbol == '.':
            uno_light.digitalWrite(pin, 0)
            sleep(0.1)
            uno_light.digitalWrite(pin, 1)
            sleep(0.1)
    sleep(0.5)

def morse_message(pin, message):
    if not uno_light:
        print(f"Simulating Morse message '{message}' on pin {pin}")
        return

    for char in message:
        if char in morse_code:
            morse_char(pin, char)
        else:
            sleep(0.2)
        sleep(0.2)

############################################################################
##############################     MAIN PROGRAM    ####################################
############################################################################

if __name__ == '__main__':
    root = Tk()
    root.title("Arduino Controller")
    root.geometry("300x200")

    frame = Frame(root)
    frame.pack()

    Button(frame, text="Start Music", command=music_start).grid(row=0, column=0)
    Button(frame, text="Stop Music", command=music_stop).grid(row=0, column=1)
    Button(frame, text="Test Music", command=music_test).grid(row=0, column=2)
    Button(frame, text="Neons All On", command=neons_all_on).grid(row=1, column=0)
    Button(frame, text="Neons All Off", command=neons_all_off).grid(row=1, column=1)
    Button(frame, text="Drill On and Off", command=drill_on_and_off).grid(row=2, column=0)

    root.mainloop()
