#include <Arduino.h>
#include <TMCStepper.h>

#define RXD2 21
#define TXD2 19
#define STEP_PIN 22
#define DIR_PIN  23

#define R_SENSE 0.11f
#define DRIVER_ADDRESS 0b00

TMC2209Stepper driver(&Serial2, R_SENSE, DRIVER_ADDRESS);

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);

  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);
  driver.begin();

  // Configuration TMC2209 - COUPLE MAXIMAL NEMA 23
  driver.toff(5);                 // Active les étages de puissance
  driver.rms_current(1300);       // 1300 mA (Proche des 1.5A max du moteur)
  driver.microsteps(8);           // 1/8ème de pas (Compromis vitesse / couple idéal)
  driver.en_spreadCycle(true);    // Mode SpreadCycle (Couple max à haute vitesse)

  Serial.println("Driver prêt. Cycle de 18 secondes par sens à couple max...");
  delay(1000);
}

void tournerPendant(unsigned long dureeMs, bool sens) {
  digitalWrite(DIR_PIN, sens ? HIGH : LOW);

  int delaiMax = 800; // Vitesse de départ lente (pour éviter les à-coups)
  int delaiMin = 120; // Vitesse rapide de croisière
  int delaiActuel = delaiMax;

  unsigned long tempsDebut = millis();

  while (millis() - tempsDebut < dureeMs) {
    // Rampe d'accélération progressive sur 500 ms
    if ((millis() - tempsDebut < 500) && (delaiActuel > delaiMin)) {
      delaiActuel -= 4;
    } 
    // Rampe de décélération douce sur 500 ms avant l'arrêt
    else if ((dureeMs - (millis() - tempsDebut) < 500) && (delaiActuel < delaiMax)) {
      delaiActuel += 4;
    }

    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(delaiActuel);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(delaiActuel);
  }
}

void loop() {
  Serial.println("Sens HORAIRE (18 secondes)...");
  tournerPendant(18000, true);
  
  Serial.println("Pause 1 sec...");
  delay(1000);

  Serial.println("Sens ANTI-HORAIRE (18 secondes)...");
  tournerPendant(18000, false);
  
  Serial.println("Pause 1 sec...");
  delay(1000);
}