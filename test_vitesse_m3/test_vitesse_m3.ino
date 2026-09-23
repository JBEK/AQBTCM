// Test vitesse + comparaison des modes de hachage — Machine 3 (S15, driver 3)
//
// Même test que test_vitesse.ino (Machine 2), mais sur Machine 3 : on
// soupçonne une alimentation (VM/GND) marginale sur ce driver précis, qui
// tient avec S23 (courant plus faible) mais fait planter l'ESP32 avec S15
// (courant plus élevé, SG_RESULT bas observé en direct = charge élevée).
//
// L'idée : StealthChop tire moins de courant que SpreadCycle à une vitesse
// donnée — si le plantage ne se produit plus en StealthChop, ça confirme
// que c'est bien une histoire de courant/alimentation sur ce driver, pas un
// problème ailleurs.
//
// Câblage Machine 3 : DIR=33, STEP=32, EN=14, adresse UART 0b01.

#include <Arduino.h>
#include <TMCStepper.h>

#define RXD2 21
#define TXD2 22
#define DIR_PIN  33
#define STEP_PIN 32
#define EN_PIN   14
#define R_SENSE 0.11f
#define DRIVER_ADDRESS 0b01

#define MICROSTEPS 8
#define PAS_PAR_TOUR 200        // NEMA23 1.8°

// ---- réglages ----
const float RPM_CROISIERE = 100.0;
const float RPM_DEPART    = 15.0;
const unsigned long RAMPE_MS     = 5000;   // montée ET descente
const unsigned long CROISIERE_MS = 10000;  // temps tenu à pleine vitesse
const unsigned long PAUSE_MS     = 2500;   // pause entre deux essais
const unsigned long PRINT_MS     = 300;    // plus fréquent qu'avant, pour bien voir un plantage venir

TMC2209Stepper driver(&Serial2, R_SENSE, DRIVER_ADDRESS);

unsigned long delaiPourRPM(float rpm) {
  float microsteps_par_s = rpm / 60.0 * PAS_PAR_TOUR * MICROSTEPS;
  return (unsigned long)(1000000.0 / microsteps_par_s);
}

void configBase() {
  driver.toff(5);
  driver.rms_current(1100);
  driver.microsteps(MICROSTEPS);
  driver.TCOOLTHRS(0xFFFFFUL);
  driver.SGTHRS(0);
}

void appliquerMode(int mode) {
  configBase();
  switch (mode) {
    case 0:  // SpreadCycle seul
      driver.en_spreadCycle(true);
      driver.intpol(false);
      break;
    case 1:  // SpreadCycle + interpolation — réglage actuel de la production
      driver.en_spreadCycle(true);
      driver.intpol(true);
      break;
    case 2:  // StealthChop + interpolation (courant plus doux)
      driver.en_spreadCycle(false);
      driver.pwm_autoscale(true);   // indispensable en StealthChop
      driver.intpol(true);
      break;
  }
}

const char* nomMode(int mode) {
  switch (mode) {
    case 0:  return "1/3 SpreadCycle seul";
    case 1:  return "2/3 SpreadCycle + intpol (reglage actuel de la production)";
    default: return "3/3 StealthChop + intpol (courant plus doux)";
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== Test vitesse + modes de hachage - Machine 3 (S15, driver 3) ===");

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);   // ENN actif bas : LOW = driver activé

  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);
  driver.begin();

  uint8_t statut = driver.test_connection();
  Serial.print("test_connection() = "); Serial.print(statut);
  Serial.println(statut == 0 ? "  -> OK" : "  -> ECHEC, verifie le cablage !");

  Serial.print("croisiere = "); Serial.print(RPM_CROISIERE, 0);
  Serial.print(" RPM | acceleration ");
  Serial.print((RPM_CROISIERE - RPM_DEPART) / (RAMPE_MS / 1000.0), 0);
  Serial.println(" RPM/s sur 5 s");
  Serial.println("Ecoute les 3 essais. Si ca plante, le mode en cours au moment");
  Serial.println("du plantage sera visible juste avant le reboot dans les logs.");
  delay(1500);
}

// Retourne false si le mouvement a ete interrompu (ne devrait pas arriver
// ici puisqu'un vrai plantage redemarre l'ESP32 entier - mais garde la
// fonction structurée pour le jour ou on ajoutera une vraie detection).
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

  digitalWrite(EN_PIN, HIGH);  // roue libre pendant la pause
}

void loop() {
  for (int mode = 0; mode < 3; mode++) {
    appliquerMode(mode);
    Serial.println();
    Serial.print("=== "); Serial.print(nomMode(mode)); Serial.println(" ===");
    tourner(mode % 2 == 0);          // alterne le sens d'un essai à l'autre
    Serial.println("--- pause ---");
    delay(PAUSE_MS);
  }
  Serial.println();
  Serial.println("### fin du cycle, on recommence ###");
  delay(PAUSE_MS);
}
