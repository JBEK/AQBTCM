from pygame import mixer
from tkinter import *
from tkinter import filedialog
from nanpy import ArduinoApi, SerialManager
from time import sleep
import threading
from threading import Thread




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
    uno_light_A = ArduinoApi(connection=slave_uno_light)
    print ("Arduino UNO LIGHT A connected")
except:
    print ("Failed to connect to Arduino UNO (Light A)")


####OUTPUT

#NEON_LIGHT
neon_A_1 = 3
neon_A_2 = 5
neon_A_3 = 6
neon_A_4 = 9

uno_light_A.pinMode(neon_A_1,uno_light_A.OUTPUT)
uno_light_A.pinMode(neon_A_2,uno_light_A.OUTPUT)
uno_light_A.pinMode(neon_A_3,uno_light_A.OUTPUT)
uno_light_A.pinMode(neon_A_4,uno_light_A.OUTPUT)

#DRILLS
pinDrill_1 = 3
pinDrill_2 = 5
pinDrill_3 = 9


mega_drill.pinMode(pinDrill_1,mega_drill.OUTPUT)
mega_drill.pinMode(pinDrill_2,mega_drill.OUTPUT)
mega_drill.pinMode(pinDrill_3,mega_drill.OUTPUT)

'''class arduino_uno_light_A :
    name = ['mega_drill']
    pin = ['pinDrill_1']
'''
    ############################################################################
##################################    FUNCTIONS DEF  #######################################
    ############################################################################



#######################################   DRILLS   ########################################################


def fading_in_and_out(name,pin):
    intensity = 0
    fadeAmount = 5
   # print ("Drill_") + [__name__] +("fading")
    print ("Start fading in and")
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

        
#go_on = 'arduino'.analogWrite(pinDrill_1, intensity)
# FIRST DRILL ON
def first_drill_prog():
    intensity = 0
    fadeAmount = 5
    print ("Drill_1 fading")
    
    for i in range (103):
    # set the brightness of pin 9:
        mega_drill.analogWrite(pinDrill_1, intensity)
    # change the brightness for next time through the loop:
        intensity += fadeAmount
    # reverse the direction of the fading at the ends of the fade: 
        if intensity == 0 or intensity == 255:
            fadeAmount = -fadeAmount         
    # wait for 30 milliseconds to see the dimming effect 
        sleep (0.03)

                        
# SECOND DRILL ON
def second_drill_prog():
    intensity = 0
    fadeAmount = 5

    for i in range(2):
        mega_drill.analogWrite(pinDrill_2, 100)   # PWM à 10/255
        sleep(1)                      # Attendre 1s
        mega_drill.analogWrite(pinDrill_2, 255)   # PWM à 50/255
        sleep(1)                      # Attendre 1s
                           # Attendre 1s

# THIRD DRILL ON
def third_drill_prog():
    intensity = 0
    fadeAmount = 5

    for i in range(2):
        mega_drill.analogWrite(pinDrill_3, 100)   # PWM à 10/255
        sleep(1)                      # Attendre 1s
        mega_drill.analogWrite(pinDrill_3, 255)   # PWM à 50/255
        sleep(1)                      # Attendre 1s
                           # Attendre 1s
   

#STOP DRILLS
def stopDrill_1():
    mega_drill.analogWrite(pinDrill_1, 0)
    print("Drill_1 off")

def stopDrill_2():
    mega_drill.analogWrite(pinDrill_2,0)
    print("Drill_2 off")

def stopDrill_3():
    mega_drill.analogWrite(pinDrill_3,0)
    print("Drill_3 off")


#####################################    MUSIC    ##################################################
# START AND FADING OUT MUSIC
def startMusic():
    mixer.init()
    mixer.music.load("aqbtcm2.mp3")
    mixer.music.set_volume(0.6)
    mixer.music.play()
    print ("Starting music")

def stopMusic():
    mixer.music.fadeout(3333)
    print ("Music stopped")

#################################### NEON LIGHTS ###############################################

def all_on_neon():
    print ("Neon_A all on")
    uno_light_A.digitalWrite(neon_A_1, 1)
    uno_light_A.digitalWrite(neon_A_2, 1)
    uno_light_A.digitalWrite(neon_A_3, 1)
    uno_light_A.digitalWrite(neon_A_4, 1)

def all_off_neon():
    print ("Neon_A all off")
    uno_light_A.digitalWrite(neon_A_1, 0)
    uno_light_A.digitalWrite(neon_A_2, 0)
    uno_light_A.digitalWrite(neon_A_3, 0)
    uno_light_A.digitalWrite(neon_A_4, 0)
    
def tralalou ():
    print ("Tralalou is running")
    uno_light_A.digitalWrite(neon_A_1, 1)
    sleep(0.05)
    uno_light_A.digitalWrite(neon_A_2, 1)
    sleep(0.05)
    uno_light_A.digitalWrite(neon_A_3, 1)
    sleep(0.05)
    uno_light_A.digitalWrite(neon_A_4, 1)
    #uno_light_A.digitalWrite(neon_A_2, (i + 1) % 2)
    sleep(0.05)
    uno_light_A.digitalWrite(neon_A_4, 0)
    sleep(0.05)
    uno_light_A.digitalWrite(neon_A_3, 0)
    sleep(0.05)
    uno_light_A.digitalWrite(neon_A_2, 0)
    sleep(0.05)
    uno_light_A.digitalWrite(neon_A_1, 0)
    sleep(0.05)

def random_neon():
    print ("Random Neon running")
    for i in range(8):
#uno_light_A.digitalWrite(neon_A_2, (i + 1) % 2)
        uno_light_A.digitalWrite(neon_A_1, 1)
        sleep(0.03)
        uno_light_A.digitalWrite(neon_A_3, 1)
        sleep(0.03)
        uno_light_A.digitalWrite(neon_A_1, 0)
        sleep(0.03)
        uno_light_A.digitalWrite(neon_A_2, 1)
        sleep(0.03)
        uno_light_A.digitalWrite(neon_A_3, 0)
        sleep(0.03)
        uno_light_A.digitalWrite(neon_A_2, 0)
        sleep(0.03)
        uno_light_A.digitalWrite(neon_A_4, 1)
        sleep(0.03)
        uno_light_A.digitalWrite(neon_A_3, 1)
        sleep(0.03)
        uno_light_A.digitalWrite(neon_A_2, 1)
        sleep(0.03)
        uno_light_A.digitalWrite(neon_A_1, 1)
        sleep(0.03)
        uno_light_A.digitalWrite(neon_A_4, 0)
        sleep(0.03)

########################################################################
############################   THREADS   ###############################
########################################################################

music_thread = threading.Thread (target=startMusic)
first_drill_thread = threading.Thread (target=first_drill_prog)
second_drill_thread =threading.Thread (target=second_drill_prog)
third_drill_thread = threading.Thread (target=third_drill_prog)


   
#########################################################################
############################### PROGRAM #################################
#########################################################################




startMusic()                        # STARTING MUSIC
sleep (1)
i=0
while i<2:
    fading_in_and_out(mega_drill,pinDrill_1)
    fading_in_and_out(mega_drill,pinDrill_2)
    fading_in_and_out(mega_drill,pinDrill_3)
    i=i+1

sleep (2)

for i in range (3) :                #STARTING FIRST DRILL
    first_drill_prog()
  
   
#second_drill_prog()
#third_drill_prog()

sleep (1)
all_on_neon()
sleep(3)
all_off_neon()
sleep (2)
for i in range (5):
    random_neon()
tralalou()
all_off_neon()




sleep (4)


# STOP MUSIC
stopMusic()
sleep (1)

#STOP DRILLS
stopDrill_1()
sleep (1)
stopDrill_2 ()

sleep (2)
'''

#music_thread.start()
#sleep (5)
#first_drill_thread.start()


slave_1.close()
slave_2.close()                      # Fermeture du port série
'''
