from pygame import mixer
from tkinter import *
from tkinter import filedialog
from nanpy import ArduinoApi, SerialManager
from time import sleep
import threading
from threading import Thread
import sys



    ############################################################################
#########################    ARDUINO  SERIAL CONNEXIONS AN OUTPUT  ##################
    ############################################################################

#i=0
#ARDUINOS

try:
    slave_mega_drill = SerialManager(device='COM8') 
    mega_drill = ArduinoApi(connection=slave_mega_drill)
    print ("Arduino MEGA DRILL connected")
except:
    print("Failed to connect to Arduino MEGA (Drill)")

try :
    slave_uno_light = SerialManager(device='COM9')
    uno_light = ArduinoApi(connection=slave_uno_light)
    print ("Arduino UNO LIGHT A connected")
except:
    print ("Failed to connect to Arduino UNO (Light A)")


####OUTPUT

#NEON_LIGHT
neon_A_1 = 8
neon_A_2 = 9
neon_A_3 = 10
neon_A_4 = 11

neon_B_1 = 2
neon_B_2 = 3
neon_B_3 = 4
neon_B_4 = 5

uno_light.pinMode(neon_A_1,uno_light.OUTPUT)
uno_light.pinMode(neon_A_2,uno_light.OUTPUT)
uno_light.pinMode(neon_A_3,uno_light.OUTPUT)
uno_light.pinMode(neon_A_4,uno_light.OUTPUT)

uno_light.pinMode(neon_B_1,uno_light.OUTPUT)
uno_light.pinMode(neon_B_2,uno_light.OUTPUT)
uno_light.pinMode(neon_B_3,uno_light.OUTPUT)
uno_light.pinMode(neon_B_4,uno_light.OUTPUT)



#DRILLS
pinDrill_1 = 3
pinDrill_2 = 5
pinDrill_3 = 9


mega_drill.pinMode(pinDrill_1,mega_drill.OUTPUT)
mega_drill.pinMode(pinDrill_2,mega_drill.OUTPUT)
mega_drill.pinMode(pinDrill_3,mega_drill.OUTPUT)


    ############################################################################
##################################    FUNCTIONS DEF  #######################################
    ############################################################################



#######################################   DRILLS   ########################################################


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
        sleep(0.1)  # Délai pour observer l'effet de fading

    for i in range(maxvalue, -1, -1):
        mega_drill.analogWrite(drill, i)
        sleep(0.1)  # Délai pour observer l'effet de fading
    i = i+1

def fade_in_and_out(drill,maxvalue):
    for i in range(0, maxvalue):
        mega_drill.analogWrite(drill, i)
        sleep(0.01)  # Délai pour observer l'effet de fading

    for i in range(maxvalue, -1, -1):
        mega_drill.analogWrite(drill, i)
        sleep(0.01)  # Délai pour observer l'effet de fading


    

#STOP DRILLS
def stopDrill_1():
    mega_drill.analogWrite(pinDrill_1, 0)
    print("Drill_1 OFF")

def stopDrill_2():
    mega_drill.analogWrite(pinDrill_2,0)
    print("Drill_2 OFF")

def stopDrill_3():
    mega_drill.analogWrite(pinDrill_3,0)
    print("Drill_3 OFF")


#####################################    MUSIC    ##################################################
# START AND FADING OUT MUSIC
def music_start():
    mixer.init()
    mixer.music.load("aqbtcm2.mp3")
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
    uno_light.digitalWrite(neon_A_1, 1)
    uno_light.digitalWrite(neon_A_2, 1)
    uno_light.digitalWrite(neon_A_3, 1)
    uno_light.digitalWrite(neon_A_4, 1)

def neons_A_off():
    print ("Neon A all OFF")
    uno_light.digitalWrite(neon_A_1, 0)
    uno_light.digitalWrite(neon_A_2, 0)
    uno_light.digitalWrite(neon_A_3, 0)
    uno_light.digitalWrite(neon_A_4, 0)
    
def neons_B_on():
    print ("Neons B all ON")
    uno_light.digitalWrite(neon_B_1, 1)
    uno_light.digitalWrite(neon_B_2, 1)
    uno_light.digitalWrite(neon_B_3, 1)
    uno_light.digitalWrite(neon_B_4, 1)

def neons_B_off():
    print ("Neons B all OFF")
    uno_light.digitalWrite(neon_B_1, 0)
    uno_light.digitalWrite(neon_B_2, 0)
    uno_light.digitalWrite(neon_B_3, 0)
    uno_light.digitalWrite(neon_B_4, 0)

def all_neons_off():
    print ("All neons (A+B) OFF")
    neons_A_off()
    neons_B_off()
    
def tralalou ():
    print ("Tralalou is running")
    uno_light.digitalWrite(neon_A_1, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_2, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_3, 1)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_4, 1)
    #uno_light.digitalWrite(neon_A_2, (i + 1) % 2)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_4, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_3, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_2, 0)
    sleep(0.08)
    uno_light.digitalWrite(neon_A_1, 0)
    sleep(0.08)

def random_neon():
    print ("Random Neon running")
    for i in range (5):
#uno_light.digitalWrite(neon_A_2, (i + 1) % 2)
        uno_light.digitalWrite(neon_A_1, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_3, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_1, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_2, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_3, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_2, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_4, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_3, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_2, 1)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_4, 0)
        sleep(0.05)
        uno_light.digitalWrite(neon_A_1, 1)
        sleep(0.05)
        
        ################################################################
##################################    TESTS   #######################################
        ################################################################

def light_test ():
    print ("Starting lightening test")
    sleep (1)
    print ("Testing neons A")
    neons_A_on ()
    sleep (2)
    neons_A_off ()
    sleep (1)
    for i in range(5) :
        random_neon ()
    sleep (1)
    print ("Testing neons B")
    sleep (1)
    neons_B_on()
    sleep (2)
    neons_B_off()
    print ("Lightening test over")
    

def drill_test ():
    print ("Testing drills")
    print ("Half power")
    sleep(0.5)
    mega_drill.analogWrite(pinDrill_1,125)
    mega_drill.analogWrite(pinDrill_2,125)
    mega_drill.analogWrite(pinDrill_3,125)
    sleep(2)
    print ("Max power")
    sleep(0.5)
    mega_drill.analogWrite(pinDrill_1,255)
    mega_drill.analogWrite(pinDrill_2,255)
    mega_drill.analogWrite(pinDrill_3,255)
    sleep(2)
    print ("All OFF")
    sleep(0.5)
    mega_drill.analogWrite(pinDrill_1,0)
    mega_drill.analogWrite(pinDrill_2,0)
    mega_drill.analogWrite(pinDrill_3,0)
    
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


########################################################################
############################   THREADS   ###############################
########################################################################

def start_loop():
    global running_thread
    running_thread = threading.Thread(target=continuous_loop)
    running_thread.start()

def stop_loop():
    global running_thread, stop_event
    if running_thread is not None:
        stop_event.set()
        running_thread.join()
        stop_event.clear()

def continuous_loop():
    global stop_event
    while not stop_event.is_set():
        print("Boucle en cours...")
        routine ()
        window.update()  # Mettre à jour la fenêtre (utile si votre boucle utilise Tkinter)

        # Délai en millisecondes pour la boucle avant de la relancer
        window.after(1000)  # La boucle s'exécute toutes les 1000 ms (1 seconde)


# Variables partagées
running_thread = None
stop_event = threading.Event()








#########################################################################
############################### PROGRAM #################################
#########################################################################

def routine():
   # fade_in(pinDrill_1,255)
    all_neons_off ()
    sleep (3)
    music_start()
    sleep(4)
    for i in range (3):
     tralalou()
    for i in range (1):
        random_neon()
    sleep (0.2)
    for i in range (6):
        tralalou ()

    sleep (4)

    all_neons_off()

    sleep (3)
                            
    '''
    fading_to_max (mega_drill,pinDrill_3)
    sleep (1)

    fading_in_and_out(mega_drill,pinDrill_1)
    fading_in_and_out(mega_drill,pinDrill_2)
    fading_in_and_out(mega_drill,pinDrill_3)
    sleep (2)

    for i in range (3) :                #STARTING FIRST DRILL
        first_drill_prog()
    sleep (1)

    for i in range (5):
        random_neon()

    tralalou()
    all_neons_off()
    sleep (4)
'''

# STOP MUSIC
    music_stop()
    sleep (1)

#STOP DRILLS
    stopDrill_1()
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
window.config(background='cyan')

frame=Frame(window, bg='cyan')
# interface = Interface(fenetre)
champ_label = Label(frame, text= "Hello dear \n What do you want to do ? \n")
champ_label.pack()


start_button = Button(frame, text="Start", command=start_loop)
start_button.pack(pady=10, fill=X)

pause_button = Button(frame, text="Pause", command=stop_loop)
pause_button.pack(pady=10, fill=X)

stop_button = Button(frame, text="Stop", command=stop_loop)
stop_button.pack(pady=10, fill=X)

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


