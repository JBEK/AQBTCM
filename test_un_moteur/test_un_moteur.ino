// Sketch de diagnostic — UN SEUL moteur, sur le modèle du tout premier test
// (working_TMC2209_UART_FULLnm_SLOW, dans archive/firmware_anciens/).
// Boucle bloquante volontairement gardée simple pour isoler un problème de
// câblage/driver, à l'écart de la machine à états du vrai firmware.
//
// Change juste MOTOR_ID pour tester un autre moteur (0, 1 ou 2) : les pins et
// l'adresse sont repris du câblage réel (voir COMMANDES.md).

#include <Arduino.h>
#include <TMCStepper.h>

#define MOTOR_ID 0   // <-- change ici : 0, 1 ou 2 selon la perceuse à tester

#define RXD2 21
#define TXD2 22
#define R_SENSE 0.11f

// câblage réel confirmé sur site (identique à esp32_motors.ino)
const uint8_t DIR_PINS[3]  = {19, 27, 33};
const uint8_t STEP_PINS[3] = {18, 26, 32};
const uint8_t EN_PINS[3]   = {5, 25, 14};
const uint8_t TMC_ADDR[3]  = {0, 1, 2};

const uint8_t DIR_PIN  = DIR_PINS[MOTOR_ID];
const uint8_t STEP_PIN = STEP_PINS[MOTOR_ID];
const uint8_t EN_PIN   = EN_PINS[MOTOR_ID];

TMC2209Stepper driver(&Serial2, R_SENSE, TMC_ADDR[MOTOR_ID]);

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.print("Test du moteur "); Serial.println(MOTOR_ID);
  Serial.print("DIR="); Serial.print(DIR_PIN);
  Serial.print(" STEP="); Serial.print(STEP_PIN);
  Serial.print(" EN="); Serial.print(EN_PIN);
  Serial.print(" adresse UART="); Serial.println(TMC_ADDR[MOTOR_ID]);

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);   // ENN actif bas : LOW = driver activé. Sans ça, le moteur ne bouge jamais.

  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);
  driver.begin();

  // test_connection() lit un registre du driver par UART : 0 = communication
  // OK, autre chose = le driver ne répond pas à cette adresse (câblage
  // MS1/MS2 à vérifier, ou RX/TX inversés, ou pas d'alimentation logique).
  uint8_t statut = driver.test_connection();
  Serial.print("test_connection() = "); Serial.print(statut);
  Serial.println(statut == 0 ? "  -> OK, le driver répond" : "  -> ÉCHEC, le driver ne répond pas à cette adresse !");

  driver.toff(5);
  driver.rms_current(1300);
  driver.microsteps(8);
  driver.en_spreadCycle(true);

  Serial.println("Driver prêt. Cycle de 18 secondes par sens à couple max...");
  delay(1000);
}

void tournerPendant(unsigned long dureeMs, bool sens) {
  digitalWrite(DIR_PIN, sens ? HIGH : LOW);

  int delaiMax = 800; // vitesse de départ lente (pour éviter les à-coups)
  int delaiMin = 120; // vitesse rapide de croisière
  int delaiActuel = delaiMax;

  unsigned long tempsDebut = millis();

  while (millis() - tempsDebut < dureeMs) {
    if ((millis() - tempsDebut < 500) && (delaiActuel > delaiMin)) {
      delaiActuel -= 4;
    } else if ((dureeMs - (millis() - tempsDebut) < 500) && (delaiActuel < delaiMax)) {
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
