// Sketch de diagnostic StallGuard — Machine 2 (S23) uniquement.
//
// Reprend exactement les pins/adresse/rampe/cycle de Machine 2 dans
// esp32_motors.ino, pour collecter des valeurs SG_RESULT représentatives des
// conditions réelles de fonctionnement (aspérités du mécanisme comprises),
// avant de coder une logique de détection/réaction dans le firmware de
// production.
//
// Aucun seuil, aucune réaction ici : on lit juste SG_RESULT en continu par
// UART pendant que le moteur tourne normalement, pour voir sa plage "normale"
// puis comparer avec un blocage volontaire à la main (voir COMMANDES.md /
// le plan de session pour le protocole de test).

#include <Arduino.h>
#include <TMCStepper.h>

#define RXD2 21
#define TXD2 22
#define R_SENSE 0.11f

// câblage réel + adresse mesurée de Machine 2 (voir esp32_motors.ino)
#define DIR_PIN  27
#define STEP_PIN 26
#define EN_PIN   25
#define DRIVER_ADDRESS 2

TMC2209Stepper driver(&Serial2, R_SENSE, DRIVER_ADDRESS);

// rampe et cycle identiques à Machine 2 en production (esp32_motors.ino)
const unsigned long CYCLE_MS[2] = {27000, 26000};  // [0]=horaire, [1]=antihoraire
const unsigned long PAUSE_MS[2] = {3000, 7000};    // pause après CE sens
const unsigned long ACCEL_MS = 5000;
const unsigned long DECEL_MS = 5000;
const int DELAI_MAX = 4000;
const int CRUISE_DELAI = 120;
const int RAMP_STEP = 2;

const unsigned long SG_PRINT_INTERVAL_MS = 50;  // fréquence des lectures StallGuard

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== Diagnostic StallGuard - Machine 2 (S23) ===");

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);  // ENN actif bas : LOW = driver activé

  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);
  driver.begin();

  uint8_t statut = driver.test_connection();
  Serial.print("test_connection() = "); Serial.print(statut);
  Serial.println(statut == 0 ? "  -> OK, le driver repond" : "  -> ECHEC, verifie le cablage avant de continuer !");

  driver.toff(5);
  driver.rms_current(1300);
  driver.microsteps(8);
  driver.en_spreadCycle(true);

  // StallGuard actif sur toute la plage de vitesse pour ce test (a resserrer
  // avec TCOOLTHRS plus tard si les lectures a basse vitesse (debut/fin de
  // rampe) s'averent trop bruitees/inutilisables)
  driver.TCOOLTHRS(0xFFFFFUL);
  driver.SGTHRS(0);  // pas de seuil/reaction ici, on lit juste SG_RESULT en continu

  Serial.println("t_ms,sens,delai_us,SG_RESULT");
  delay(500);
}

void tournerPendant(unsigned long dureeMs, bool horaire) {
  digitalWrite(DIR_PIN, horaire ? HIGH : LOW);

  int delaiActuel = DELAI_MAX;
  unsigned long tempsDebut = millis();
  unsigned long dernierPrint = 0;
  unsigned long dernierStepMicros = micros();

  while (millis() - tempsDebut < dureeMs) {
    unsigned long elapsed = millis() - tempsDebut;

    // même timing que updateMotor() en production : impulsion fixe de 2µs,
    // l'intervalle entre 2 pas est directement delaiActuel (pas 2x comme
    // dans l'ancien script d'origine) — sinon la rampe tourne 2x plus
    // lentement ici qu'en vrai et n'atteint jamais CRUISE_DELAI à temps.
    unsigned long nowMicros = micros();
    if (nowMicros - dernierStepMicros >= (unsigned long)delaiActuel) {
      if (elapsed < ACCEL_MS && delaiActuel > CRUISE_DELAI) {
        delaiActuel = max(CRUISE_DELAI, delaiActuel - RAMP_STEP);
      } else if ((dureeMs - elapsed) < DECEL_MS && delaiActuel < DELAI_MAX) {
        delaiActuel = min(DELAI_MAX, delaiActuel + RAMP_STEP);
      }
      digitalWrite(STEP_PIN, HIGH);
      delayMicroseconds(2);
      digitalWrite(STEP_PIN, LOW);
      dernierStepMicros = nowMicros;
    }

    if (millis() - dernierPrint >= SG_PRINT_INTERVAL_MS) {
      uint16_t sg = driver.SG_RESULT();
      Serial.print(millis()); Serial.print(",");
      Serial.print(horaire ? "horaire" : "antihoraire"); Serial.print(",");
      Serial.print(delaiActuel); Serial.print(",");
      Serial.println(sg);
      dernierPrint = millis();
    }
  }
}

void loop() {
  Serial.println("--- Sens HORAIRE (27s) ---");
  tournerPendant(CYCLE_MS[0], true);
  digitalWrite(EN_PIN, HIGH);
  Serial.print("--- Pause "); Serial.print(PAUSE_MS[0] / 1000); Serial.println("s ---");
  delay(PAUSE_MS[0]);
  digitalWrite(EN_PIN, LOW);

  Serial.println("--- Sens ANTIHORAIRE (26s) ---");
  tournerPendant(CYCLE_MS[1], false);
  digitalWrite(EN_PIN, HIGH);
  Serial.print("--- Pause "); Serial.print(PAUSE_MS[1] / 1000); Serial.println("s ---");
  delay(PAUSE_MS[1]);
  digitalWrite(EN_PIN, LOW);
}
