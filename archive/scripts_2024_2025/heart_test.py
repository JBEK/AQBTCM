import serial
import time

ser = serial.Serial('COM6', 9600)
time.sleep(2)

with open("heart.txt", "r") as f:
    for line in f:
        value = line.strip()
        if value.isdigit():
            ser.write(f"{value}\n".encode())
            time.sleep(0.02)  # 10 ms entre chaque valeur ≈ 100 Hz
