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

try:
    slave_mega_drill = SerialManager(device='COM9') 
    mega_drill = ArduinoApi(connection=slave_mega_drill)
    print ("Arduino MEGA DRILL connected")
except:
    print("Failed to connect to Arduino MEGA (Drill)")
   

try :
    slave_uno_light = SerialManager(device='COM8')
    uno_light = ArduinoApi(connection=slave_uno_light)
    print ("Arduino UNO LIGHT A connected")
except:
    print ("Failed to connect to Arduino UNO (Light A)")


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

uno_light.pinMode(neon_A_1,uno_light.OUTPUT)
uno_light.pinMode(neon_A_2,uno_light.OUTPUT)
uno_light.pinMode(neon_A_3,uno_light.OUTPUT)
uno_light.pinMode(neon_A_4,uno_light.OUTPUT)

uno_light.pinMode(neon_B_1,uno_light.OUTPUT)
uno_light.pinMode(neon_B_2,uno_light.OUTPUT)
uno_light.pinMode(neon_B_3,uno_light.OUTPUT)
uno_light.pinMode(neon_B_4,uno_light.OUTPUT)

uno_light.pinMode(neon_C_1,uno_light.OUTPUT)
uno_light.pinMode(neon_C_2,uno_light.OUTPUT)
uno_light.pinMode(neon_C_3,uno_light.OUTPUT)
uno_light.pinMode(neon_C_4,uno_light.OUTPUT)



#DRILLS
drill_1 = 3
drill_2 = 5
drill_3 = 9

#try :
 #   mega_drill.pinMode(drill_1,mega_drill.OUTPUT)
  #  mega_drill.pinMode(drill_2,mega_drill.OUTPUT)
   # mega_drill.pinMode(drill_3,mega_drill.OUTPUT)

#except :
 #   print("Failed set Arduino MEGA DRILL OUTPUTS")

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
    mega_drill.analogWrite(drill_1,200)
    mega_drill.analogWrite(drill_2,200)
    mega_drill.analogWrite(drill_3,200)
    sleep(4)
    print ("MAX POWER")
    sleep(0.5)
    mega_drill.analogWrite(drill_1,255)
    mega_drill.analogWrite(drill_2,255)
    mega_drill.analogWrite(drill_3,255)
    sleep(6)
    print ("All OFF")
    sleep(4)
    mega_drill.analogWrite(drill_1,0)
    mega_drill.analogWrite(drill_2,0)
    mega_drill.analogWrite(drill_3,0)

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
        mega_drill.analogWrite(drill, i)
        sleep(3)  # Délai pour observer l'effet de fading

    for i in range(maxvalue, -1, -1):
        mega_drill.analogWrite(drill, i)
        sleep(3)  # Délai pour observer l'effet de fading
    i = i+1

def fade_in_and_out(drill,maxvalue):
    for i in range(0, maxvalue):
        mega_drill.analogWrite(drill, i)
        sleep(0.01)  # Délai pour observer l'effet de fading

    for i in range(maxvalue, -1, -1):
        mega_drill.analogWrite(drill, i)
        sleep(0.01)  # Délai pour observer l'effet de fading
  

#STOP DRILLS
def stopdrill_1():
    mega_drill.analogWrite(drill_1, 0)
    print("drill_1 OFF")

def stopDrill_2():
    mega_drill.analogWrite(drill_2,0)
    print("Drill_2 OFF")

def stopDrill_3():
    mega_drill.analogWrite(drill_3,0)
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

def neons_A_on():
    print ("Neon A all ON")
    uno_light.digitalWrite(neon_A_1, 0)
    uno_light.digitalWrite(neon_A_2, 0)
    uno_light.digitalWrite(neon_A_3, 0)
    uno_light.digitalWrite(neon_A_4, 0)

def neons_A_off():
    print ("Neon A all OFF")
    uno_light.digitalWrite(neon_A_1, 1)
    uno_light.digitalWrite(neon_A_2, 1)
    uno_light.digitalWrite(neon_A_3, 1)
    uno_light.digitalWrite(neon_A_4, 1)
    
def neons_B_on():
    print ("Neons B all ON")
    uno_light.digitalWrite(neon_B_1, 0)
    uno_light.digitalWrite(neon_B_2, 0)
    uno_light.digitalWrite(neon_B_3, 0)
    uno_light.digitalWrite(neon_B_4, 0)

def neons_B_off():
    print ("Neons B all OFF")
    uno_light.digitalWrite(neon_B_1, 1)
    uno_light.digitalWrite(neon_B_2, 1)
    uno_light.digitalWrite(neon_B_3, 1)
    uno_light.digitalWrite(neon_B_4, 1)

def neons_C_on():
    print ("Neon A all ON")
    uno_light.digitalWrite(neon_C_1, 0)
    uno_light.digitalWrite(neon_C_2, 0)
    uno_light.digitalWrite(neon_C_3, 0)
    uno_light.digitalWrite(neon_C_4, 0)

def neons_C_off():
    print ("Neon A all OFF")
    uno_light.digitalWrite(neon_C_1, 1)
    uno_light.digitalWrite(neon_C_2, 1)
    uno_light.digitalWrite(neon_C_3, 1)
    uno_light.digitalWrite(neon_C_4, 1)

def all_neons_on():
    print ("All neons ON")
    neons_A_on()
    neons_B_on()
    neons_C_on()

def all_neons_off():
    print ("All neons OFF")
    neons_A_off()
    neons_B_off()
    neons_C_off()


def tralalou ():
    print ("Tralalou is running")
    uno_light.digitalWrite(neon_A_1, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_B_1, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_C_1, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_2, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_B_2, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_C_2, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_3, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_B_3, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_C_3, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_4, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_B_4, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_C_4, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_4, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_B_4, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_C_4, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_3, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_B_3, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_C_3, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_2, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_B_2, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_C_2, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_1, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_B_1, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_C_1, 0)
    sleep(0.08)

def false_random_neon():
    print ("Random Neon running")
    for i in range (5):
#uno_light.digitalWrite(neon_A_2, (i + 1) % 2)
        uno_light.digitalWrite(neon_A_1, 1)
        sleep(0.08)
        uno_light.digitalWrite(neon_B_1, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_3, 1)
        sleep(0.08)
        uno_light.digitalWrite(neon_B_3, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_4, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_B_4, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_1, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_B_1, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_2, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_B_2, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_3, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_B_3, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_2, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_B_2, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_3, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_B_3, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_2, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_B_2, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_4, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_B_4, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_1, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_B_1, 1)
        sleep(0.05)

def random_blink():
    while True:
        randNum1 = random.choice([True, False])
        randNum2 = random.choice([True, False])
        randNum3 = random.choice([True, False])
        randNum4 = random.choice([True, False])

    #print("Num 1")
    #print(randNum1)
    #print("Num 2")
    #print(randNum2)
        print()     #added to slow things down a bit.
        sleep(0.1)
        if randNum1 == True:
            uno_light.digitalWrite(neon_A_1, 1)
            uno_light.digitalWrite(neon_B_1, 1)
            uno_light.digitalWrite(neon_C_1, 1)
            if randNum2 == True:
                uno_light.digitalWrite(neon_A_2, 1)
                uno_light.digitalWrite(neon_B_2, 1)
                uno_light.digitalWrite(neon_C_2, 1)
                if randNum3 == True:
                    uno_light.digitalWrite(neon_A_3,1)
                    uno_light.digitalWrite(neon_B_3,1)
                    uno_light.digitalWrite(neon_C_3,1)
                    if randNum4 == True :
                        uno_light.digitalWrite(neon_A_4,1)
                        uno_light.digitalWrite(neon_B_4,1)
                        uno_light.digitalWrite(neon_C_4,1)
            
                    else:
                        uno_light.digitalWrite(neon_A_4,0)
                        uno_light.digitalWrite(neon_B_4,0)
                        uno_light.digitalWrite(neon_C_4,0)  
                else : 
                    uno_light.digitalWrite(neon_A_3,0)
                    uno_light.digitalWrite(neon_B_3,0)
                    uno_light.digitalWrite(neon_C_3,0)
            else:
                uno_light.digitalWrite(neon_A_2, 0)
                uno_light.digitalWrite(neon_B_2, 0)
                uno_light.digitalWrite(neon_C_2, 0)
            
        
        else:
            uno_light.digitalWrite(neon_A_1, 0)
            uno_light.digitalWrite(neon_B_1, 0)
            uno_light.digitalWrite(neon_C_1, 0)
 
# Dictionnaire de correspondance Morse


def send_morse(char):
    if char == '.':
        uno_light.digitalWrite(neon_A_1, uno_light.HIGH)  # Allume la LED pour un point
        sleep(0.1)  # Durée d'un point en secondes (ajustez selon vos besoins)
        uno_light.digitalWrite(neon_A_1, uno_light.LOW)  # Éteint la LED
        sleep(0.1)  # Attendez un court instant entre les signaux morse
    elif char == '-':
        uno_light.digitalWrite(neon_A_1, uno_light.HIGH)  # Allume la LED pour un tiret
        sleep(0.3)  # Durée d'un tiret en secondes (ajustez selon vos besoins)
        uno_light.digitalWrite(neon_A_1, uno_light.LOW)  # Éteint la LED
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
    uno_light.close()


def both_drill_and_lights ():
    tralalou()
    drill_on_and_off()

        ################################################################
##################################    TESTS   #######################################
        ################################################################

def light_test ():
    print ("Starting lightening test")
    sleep (1)
    all_neons_off()
    sleep(2)
    print ("Testing neons A")
    neons_A_on ()
    sleep (2)
    neons_A_off ()
    sleep (1)
    print ("Testing neons B")
    sleep (1)
    neons_B_on()
    sleep (2)
    neons_B_off()
    sleep (1)
    print ("Testing neons C")
    sleep (1)
    neons_C_on()
    sleep (2)
    neons_C_off()
    sleep (1)
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
    mega_drill.analogWrite(drill_1,125)
    mega_drill.analogWrite(drill_2,125)
    mega_drill.analogWrite(drill_3,125)
    sleep(2)
    print ("Max power")
    sleep(0.5)
    mega_drill.analogWrite(drill_1,255)
    mega_drill.analogWrite(drill_2,255)
    mega_drill.analogWrite(drill_3,255)
    sleep(2)
    print ("All OFF")
    sleep(0.5)
    mega_drill.analogWrite(drill_1,0)
    mega_drill.analogWrite(drill_2,0)
    mega_drill.analogWrite(drill_3,0)
    
def shutting_down_everything () :
    try :
        mega_drill.close()
        print ("Mega Drill disconnected")
    except :
        print ("Couldn't disconnect Mega Drill")

    try :
        uno_light.close()
        print ("Uno Light A disconnected")
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
    random_blink()
    sleep (4)
    all_neons_off()
    sleep(5)
    for i in range (3):
     tralalou()
    sleep (4)
    for i in range (1):
        false_random_neon()
    sleep (0.2)
    random_blink()
    sleep (4)

    all_neons_off()

    sleep (3)
                            
    '''
    fading_to_max (mega_drill,drill_3)
    sleep (1)

    fading_in_and_out(mega_drill,drill_1)
    fading_in_and_out(mega_drill,drill_2)
    fading_in_and_out(mega_drill,drill_3)
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


start_button = Button(frame, text="Start", command=start_loop)
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


