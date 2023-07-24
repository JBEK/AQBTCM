from pygame import mixer
from nanpy import ArduinoApi, SerialManager
from time import sleep


slave_1 = SerialManager(device='COM9')
slave_2 = SerialManager(device='COM8')           # Sélection du port série à modifier

#connection_1 = SerialManager(device=slave_1)
#connection_2 = SerialManager(device=slave_2)

uno_1 = ArduinoApi(connection=slave_1)            # Déclaration de la carte Arduino Uno
mega_1 = ArduinoApi(connection=slave_2) 


pinDrill_1 = 11                                  # Led branchée sur broche 11
intensity = 0
fadeAmount = 5 

pin_relay_1 = 3
pin_relay_2 = 4

#DRILLS OUTPUT ON
uno_1.pinMode(pinDrill_1, uno_1.OUTPUT)              # Broche Led en sortie
mega_1.pinMode(pinDrill_1, mega_1.OUTPUT)

#LIGHTS NEON OUTPUT ON
uno_1.pinMode(pin_relay_1,uno_1.OUTPUT)

#STOP DRILLS
def stopDrill_1():
    uno_1.analogWrite(pinDrill_1, 0)
    print("Drill_1 stopped")

def stopDrill_2():
    mega_1.analogWrite(pinDrill_1,0)
    print("Drill_2 stopped")



# START AND FADING OUT MUSIC
def startMusic():
    mixer.init()
    mixer.music.load("aqbtcm2.mp3")
    mixer.music.set_volume(0.6)
    mixer.music.play()

def stopMusic():
    mixer.music.fadeout(3333)
    print ("Music stopped")

# LIGHTS ON AND OFF (NEON)

def first_light_on():
    uno_1.digitalWrite(pin_relay_1,1)

def sec_light_on():
    uno_1.digitalWrite(pin_relay_2,1)

def first_light_off():
    uno_1.digitalWrite(pin_relay_1,0)

def sec_light_off():
    uno_1.digitalWrite(pin_relay_2,0)


    
#p.play()

startMusic()

sleep (2)

#while True :
for i in range (3):
    uno_1.analogWrite(pinDrill_1, intensity)  # PWM à 200/255
    intensity = intensity + fadeAmount
    if intensity <= 0 or intensity >= 255:	        
        fadeAmount = -fadeAmount
    sleep(3)
    uno_1.analogWrite(pinDrill_1, 0)
                          # Attendre 1s
 
#mixer.music.set_volume(0.2)

for i in range(2):
   
    mega_1.analogWrite(pinDrill_1, 10)   # PWM à 10/255
    sleep(1)                      # Attendre 1s
    mega_1.analogWrite(pinDrill_1, 50)   # PWM à 50/255
    sleep(1)                      # Attendre 1s
    mega_1.analogWrite(pinDrill_1, 255)   # PWM à 50/255
    sleep(1)                      # Attendre 1s
    '''
    mega_1.analogWrite(pinDrill_1, 255)  # PWM à 200/255
    sleep(1)  
    mega_1.analogWrite(pinDrill_1, 100)  # PWM à 200/255
    sleep(1) 
'''
#mixer.music.unpause()
sleep (4)
stopMusic()
sleep (1)
stopDrill_1()
sleep (1)
stopDrill_2 ()

sleep (4)

slave_1.close()
slave_2.close()                      # Fermeture du port série