// Test générique d'un moteur NEMA23 1.6 Nm / 1.5 A, tel qu'on testerait
// n'importe quel moteur pas-à-pas sur banc — indépendant de toute perceuse,
// de tout cycle, de toute logique d'installation. Juste : le moteur tourne-t-il
// proprement, dans les deux sens, à une vitesse raisonnable, sans décrocher ?
//
// Change MOTOR_ID (0, 1 ou 2) pour tester un autre moteur : pins et adresse
// UART repris du câblage réel confirmé (voir esp32_motors.ino).
//
// Réglages repris de ce qu'on a validé cette session comme sûrs pour ce
// moteur (1.5 A nominal) :
//   - rms_current(1100) : 1100 mA RMS ~= 1.55 A crête ~= courant nominal
//   - SpreadCycle (couple garanti, régulation active du courant) : c'est le
//     mode a utiliser pour un test de sante mecanique, StealthChop pourrait
//     masquer un decrochage en baissant le couple sans le signaler
//   - rampe a acceleration CONSTANTE (pas de décrément par pas, qui s'emballe)
//   - le driver reste actif (couple de maintien) tout du long, y compris
//     pendant la pause entre les deux sens

#include <Arduino.h>
#include <TMCStepper.h>

#define MOTOR_ID 0   // <-- change ici : 0, 1 ou 2

#define RXD2 21
#define TXD2 22
#define R_SENSE 0.11f
#define MICROSTEPS 8
#define PAS_PAR_TOUR 200   // NEMA23 1.8°

// câblage réel confirmé sur site (identique à esp32_motors.ino)
const uint8_t DIR_PINS[3]  = {19, 27, 33};
const uint8_t STEP_PINS[3] = {18, 26, 32};
const uint8_t EN_PINS[3]   = {5, 25, 14};
const uint8_t TMC_ADDR[3]  = {0, 2, 1};   // adresses 1 et 2 physiquement inversées

const uint8_t DIR_PIN  = DIR_PINS[MOTOR_ID];
const uint8_t STEP_PIN = STEP_PINS[MOTOR_ID];
const uint8_t EN_PIN   = EN_PINS[MOTOR_ID];

// ---- profil de vitesse ----
const float RPM_CROISIERE = 100.0;
const float RPM_DEPART    = 15.0;
const unsigned long RAMPE_MS     = 5000;
const unsigned long CROISIERE_MS = 10000;
const unsigned long PAUSE_MS     = 3000;
const unsigned long PRINT_MS     = 500;

TMC2209Stepper driver(&Serial2, R_SENSE, TMC_ADDR[MOTOR_ID]);

unsigned long delaiPourRPM(float rpm) {
  float microsteps_par_s = rpm / 60.0 * PAS_PAR_TOUR * MICROSTEPS;
  return (unsigned long)(1000000.0 / microsteps_par_s);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.print("=== Test generique NEMA23 - moteur "); Serial.print(MOTOR_ID);
  Serial.println(" ===");
  Serial.print("DIR="); Serial.print(DIR_PIN);
  Serial.print(" STEP="); Serial.print(STEP_PIN);
  Serial.print(" EN="); Serial.print(EN_PIN);
  Serial.print(" adresse UART="); Serial.println(TMC_ADDR[MOTOR_ID]);

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);

  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);
  driver.begin();

  uint8_t statut = driver.test_connection();
  Serial.print("test_connection() = "); Serial.print(statut);
  Serial.println(statut == 0 ? "  -> OK, le driver repond" : "  -> ECHEC, verifie le cablage !");

  driver.toff(5);
  driver.rms_current(1100);
  driver.microsteps(MICROSTEPS);
  driver.en_spreadCycle(true);
  driver.intpol(true);
  driver.TCOOLTHRS(0xFFFFFUL);
  driver.SGTHRS(0);

  Serial.print("Croisiere "); Serial.print(RPM_CROISIERE, 0);
  Serial.println(" RPM, SpreadCycle+intpol. Cycle horaire/antihoraire en boucle.");
  delay(1000);
}

void tourner(bool horaire) {
  digitalWrite(DIR_PIN, horaire ? HIGH : LOW);
  digitalWrite(EN_PIN, LOW);

  const unsigned long duree_totale = RAMPE_MS + CROISIERE_MS + RAMPE_MS;
  unsigned long debut = millis();
  unsigned long dernierStep = micros();
  unsigned long dernierPrint = 0;

  while (millis() - debut < duree_totale) {
    unsigned long t = millis() - debut;

    float rpm;
    if (t < RAMPE_MS) {
      rpm = RPM_DEPART + (RPM_CROISIERE - RPM_DEPART) * (t / (float)RAMPE_MS);
    } else if (t < RAMPE_MS + CROISIERE_MS) {
      rpm = RPM_CROISIERE;
    } else {
      float f = (t - RAMPE_MS - CROISIERE_MS) / (float)RAMPE_MS;
      rpm = RPM_CROISIERE - (RPM_CROISIERE - RPM_DEPART) * f;
    }
    if (rpm < RPM_DEPART) rpm = RPM_DEPART;

    unsigned long delai = delaiPourRPM(rpm);

    unsigned long now = micros();
    if (now - dernierStep >= delai) {
      digitalWrite(STEP_PIN, HIGH);
      delayMicroseconds(2);
      digitalWrite(STEP_PIN, LOW);
      dernierStep = now;
    }

    if (millis() - dernierPrint >= PRINT_MS) {
      Serial.print("  RPM="); Serial.print(rpm, 0);
      Serial.print("  delai="); Serial.print(delai);
      Serial.print("us  SG="); Serial.println(driver.SG_RESULT());
      dernierPrint = millis();
    }
  }
}

void loop() {
  Serial.println();
  Serial.println(">>> HORAIRE <<<");
  tourner(true);

  Serial.println("--- pause ---");
  delay(PAUSE_MS);

  Serial.println();
  Serial.println(">>> ANTI-HORAIRE <<<");
  tourner(false);

  Serial.println("--- pause ---");
  delay(PAUSE_MS);
}
