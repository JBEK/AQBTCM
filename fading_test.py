from nanpy import ArduinoApi, SerialManager
from time import sleep

led = 3
brightness = 0 
fadeAmount = 5
#baud = 9600
slave_2 = SerialManager(device='COM9') 
mega_drill = ArduinoApi(connection=slave_2)
mega_drill.pinMode(led,mega_drill.OUTPUT)
# SETUP:
i=0
# LOOP:
for i in range (103):
    # set the brightness of pin 9:
    mega_drill.analogWrite(led, brightness)
    # change the brightness for next time through the loop:
    brightness += fadeAmount
    # reverse the direction of the fading at the ends of the fade: 
    if brightness == 0 or brightness == 255:
        fadeAmount = -fadeAmount
    # wait for 30 milliseconds to see the dimming effect 
    sleep (0.03)
    #i += 1
    