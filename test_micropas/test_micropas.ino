// Test comparaison du nombre de micropas — un moteur au choix
//
// Le ta-ta-ta entendu au demarrage/en continu sur les 3 machines est la
// signature normale du mode SpreadCycle (couple garanti). Ce test compare
// a l'oreille, sur le meme profil de mouvement et le meme mode (SpreadCycle
// + intpol = reglage de production), 3 niveaux de micropas :
//   8, 16, 32
// Plus de micropas = pas plus petits = grain plus fin, sans perte de couple
// (le micropas ne change que la resolution, pas le courant).
//
// Change MOTOR_ID (0, 1 ou 2) pour tester un autre moteur : pins et adresse
// UART repris du cablage reel confirme (voir esp32_motors.ino).

#include <Arduino.h>
#include <TMCStepper.h>

#define MOTOR_ID 1   // <-- change ici : 0, 1 ou 2

#define RXD2 21
#define TXD2 22
#define R_SENSE 0.11f

#define PAS_PAR_TOUR 200        // NEMA23 1.8°

// cablage reel confirme sur site (identique a esp32_motors.ino)
const uint8_t DIR_PINS[3]  = {19, 27, 33};
const uint8_t STEP_PINS[3] = {18, 26, 32};
const uint8_t EN_PINS[3]   = {5, 25, 14};
const uint8_t TMC_ADDR[3]  = {0, 2, 1};   // adresses 1 et 2 physiquement inversees

const uint8_t DIR_PIN  = DIR_PINS[MOTOR_ID];
const uint8_t STEP_PIN = STEP_PINS[MOTOR_ID];
const uint8_t EN_PIN   = EN_PINS[MOTOR_ID];

const int MICROPAS_A_TESTER[3] = {8, 16, 32};

// ---- profil de mouvement (identique pour les 3 essais) ----
const float RPM_CROISIERE = 100.0;
const float RPM_DEPART    = 15.0;
const unsigned long RAMPE_MS     = 5000;
const unsigned long CROISIERE_MS = 10000;
const unsigned long PAUSE_MS     = 2500;
const unsigned long PRINT_MS     = 1000;

int microsteps_actuels = 8;

TMC2209Stepper driver(&Serial2, R_SENSE, TMC_ADDR[MOTOR_ID]);

unsigned long delaiPourRPM(float rpm) {
  float microsteps_par_s = rpm / 60.0 * PAS_PAR_TOUR * microsteps_actuels;
  return (unsigned long)(1000000.0 / microsteps_par_s);
}

void appliquerMicropas(int microsteps) {
  microsteps_actuels = microsteps;
  driver.toff(5);
  driver.rms_current(1100);
  driver.microsteps(microsteps);
  driver.TCOOLTHRS(0xFFFFFUL);
  driver.SGTHRS(0);
  driver.en_spreadCycle(true);   // reglage de production : SpreadCycle + intpol
  driver.intpol(true);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.print("=== Test micropas (8 / 16 / 32) - moteur "); Serial.print(MOTOR_ID);
  Serial.println(" ===");

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);

  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);
  driver.begin();

  uint8_t statut = driver.test_connection();
  Serial.print("test_connection() = "); Serial.print(statut);
  Serial.println(statut == 0 ? "  -> OK" : "  -> ECHEC, verifie le cablage !");

  Serial.println("Ecoute les 3 essais et dis lequel sonne le plus doux.");
  delay(1500);
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
  for (int i = 0; i < 3; i++) {
    appliquerMicropas(MICROPAS_A_TESTER[i]);
    Serial.println();
    Serial.println("################################################");
    Serial.print(">>> ESSAI "); Serial.print(i + 1);
    Serial.print("/3 : "); Serial.print(MICROPAS_A_TESTER[i]);
    Serial.println(" MICROPAS <<<");
    Serial.println("################################################");
    tourner(i % 2 == 0);
    Serial.println("--- pause ---");
    delay(PAUSE_MS);
  }
  Serial.println();
  Serial.println("### fin du cycle, on recommence ###");
  delay(PAUSE_MS);
}
