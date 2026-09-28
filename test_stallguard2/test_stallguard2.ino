// Mesure StallGuard — Machine 2 (S23), profil REEL d'aujourd'hui.
//
// But : savoir si SG_RESULT permet de distinguer un fonctionnement normal d'un
// blocage sur ces mecanismes de perceuse. Deux inconnues a lever :
//   1. reste-t-il de la MARGE ? (les valeurs vues en passant etaient a 0-22 sur
//      une echelle de 0-510, ce qui ne laisserait rien pour detecter un blocage)
//   2. la mesure est-elle valide en SpreadCycle ? Sur le TMC2209, StallGuard4
//      est specifie pour StealthChop. On alterne donc les deux modes d'un cycle
//      a l'autre pour comparer.
//
// Ce sketch lit SG_RESULT par UART, ce qui est BLOQUANT : acceptable ici (un
// seul moteur, outil de mesure), interdit dans esp32_motors.ino ou cela gelait
// les impulsions des 3 moteurs.
//
// Cablage Machine 2 : DIR=27, STEP=26, EN=25, adresse UART 2.
// DIAG du driver -> GPIO 4 (entree avec rappel vers le bas : si DIAG est en
// collecteur ouvert sur la carte, l'entree ne flotte pas).

#include <Arduino.h>
#include <TMCStepper.h>

#define RXD2 21
#define TXD2 22
#define DIR_PIN  27
#define STEP_PIN 26
#define EN_PIN   25
#define DIAG_PIN 4
#define R_SENSE 0.11f
#define DRIVER_ADDRESS 2

#define MICROSTEPS 8
#define PAS_PAR_TOUR 200

// declaration anticipee : Arduino hisse les prototypes des fonctions en haut du
// fichier, donc tourner(bool, Stats&, Stats&) doit connaitre Stats des ici
struct Stats;

// profil identique a la production : 20s par sens, rampe de 5s de chaque cote,
// donc 10s de croisiere - la seule plage ou StallGuard est valide
const float RPM_CROISIERE = 120.0;
const float RPM_DEPART    = 15.0;
const unsigned long ACCEL_MS  = 5000;
const unsigned long DECEL_MS  = 5000;
const unsigned long CYCLE_MS  = 20000;
const unsigned long PAUSE_MS  = 3000;
const unsigned long MESURE_MS = 50;

// Seuil provisoire, seulement pour voir si DIAG se leve a tort en
// fonctionnement normal. Le vrai seuil sera calcule a partir des mesures.
const uint8_t SGTHRS_ESSAI = 50;

TMC2209Stepper driver(&Serial2, R_SENSE, DRIVER_ADDRESS);

unsigned long delaiPourRPM(float rpm) {
  return (unsigned long)(1000000.0 / (rpm / 60.0 * PAS_PAR_TOUR * MICROSTEPS));
}

void appliquerMode(bool spreadCycle) {
  driver.toff(5);
  driver.rms_current(1100);
  driver.microsteps(MICROSTEPS);
  driver.intpol(true);
  if (spreadCycle) {
    driver.en_spreadCycle(true);
  } else {
    driver.en_spreadCycle(false);
    driver.pwm_autoscale(true);   // indispensable en StealthChop
  }
  driver.TCOOLTHRS(0xFFFFFUL);    // StallGuard actif sur toute la plage
  driver.SGTHRS(SGTHRS_ESSAI);
}

// statistiques separees rampe / croisiere : StallGuard n'est pas valide a basse
// vitesse, donc melanger les deux fausserait le seuil
struct Stats {
  uint16_t mini = 65535, maxi = 0;
  unsigned long somme = 0, n = 0;
  int diag = 0;
  void ajoute(uint16_t v, bool d) {
    if (v < mini) mini = v;
    if (v > maxi) maxi = v;
    somme += v; n++;
    if (d) diag++;
  }
  void afficher(const char* nom) {
    if (!n) { Serial.print(nom); Serial.println(" : aucune mesure"); return; }
    Serial.print("  "); Serial.print(nom);
    Serial.print(" : min="); Serial.print(mini);
    Serial.print("  max="); Serial.print(maxi);
    Serial.print("  moyenne="); Serial.print(somme / n);
    Serial.print("  DIAG leve sur "); Serial.print(diag);
    Serial.print("/"); Serial.print(n); Serial.println(" lectures");
  }
};

float rpmConsigne(unsigned long t) {
  float ecart = RPM_CROISIERE - RPM_DEPART;
  if (t < ACCEL_MS)              return RPM_DEPART + ecart * ((float)t / ACCEL_MS);
  if (CYCLE_MS - t < DECEL_MS)   return RPM_DEPART + ecart * ((float)(CYCLE_MS - t) / DECEL_MS);
  return RPM_CROISIERE;
}

// Mis a vrai des qu'un octet arrive sur le port serie : sert d'arret d'urgence.
// Le sketch precedent tournait en boucle sans jamais lire le port, donc quand la
// perceuse s'est coincee dans son cable il n'y avait aucun moyen de l'arreter
// autrement qu'en coupant le 24V.
bool arreteParOperateur = false;

bool stopDemande() {
  if (Serial.available()) {
    while (Serial.available()) Serial.read();
    arreteParOperateur = true;
    digitalWrite(EN_PIN, HIGH);   // driver coupe immediatement
    Serial.println();
    Serial.println("### ARRET DEMANDE : driver coupe ###");
  }
  return arreteParOperateur;
}

void tourner(bool horaire, Stats& rampe, Stats& croisiere) {
  digitalWrite(DIR_PIN, horaire ? HIGH : LOW);
  digitalWrite(EN_PIN, LOW);

  unsigned long debut = millis();
  unsigned long dernierStep = micros(), derniereMesure = 0;

  while (millis() - debut < CYCLE_MS) {
    if (stopDemande()) return;
    unsigned long t = millis() - debut;
    float rpm = rpmConsigne(t);
    unsigned long delai = delaiPourRPM(rpm);

    unsigned long now = micros();
    if (now - dernierStep >= delai) {
      digitalWrite(STEP_PIN, HIGH);
      delayMicroseconds(2);
      digitalWrite(STEP_PIN, LOW);
      dernierStep = now;
    }

    if (millis() - derniereMesure >= MESURE_MS) {
      uint16_t sg = driver.SG_RESULT();
      bool diag = digitalRead(DIAG_PIN);
      bool en_croisiere = (t >= ACCEL_MS) && (CYCLE_MS - t >= DECEL_MS);
      (en_croisiere ? croisiere : rampe).ajoute(sg, diag);
      // CSV : t_ms,phase,rpm,SG_RESULT,DIAG
      Serial.print(t); Serial.print(",");
      Serial.print(en_croisiere ? "croisiere" : "rampe"); Serial.print(",");
      Serial.print(rpm, 0); Serial.print(",");
      Serial.print(sg); Serial.print(",");
      Serial.println(diag ? 1 : 0);
      derniereMesure = millis();
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== Mesure StallGuard - Machine 2, profil reel (120 RPM) ===");

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  pinMode(DIAG_PIN, INPUT_PULLDOWN);
  digitalWrite(EN_PIN, LOW);

  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);
  driver.begin();

  uint8_t statut = driver.test_connection();
  Serial.print("test_connection() = "); Serial.print(statut);
  Serial.println(statut == 0 ? "  -> OK" : "  -> ECHEC, verifie le cablage !");
  Serial.print("SGTHRS d'essai = "); Serial.println(SGTHRS_ESSAI);
  Serial.println("Si DIAG se leve souvent en croisiere NORMALE, le seuil est trop haut.");
  delay(1500);
}

bool mesureFaite = false;

void loop() {
  if (mesureFaite || arreteParOperateur) {
    digitalWrite(EN_PIN, HIGH);   // rien ne tourne tant qu'on ne relance pas la carte
    delay(200);
    return;
  }

  for (int mode = 0; mode < 2; mode++) {
    if (arreteParOperateur) break;
    bool spread = (mode == 0);
    appliquerMode(spread);
    Serial.println();
    Serial.println("################################################");
    Serial.print(">>> MODE ");
    Serial.print(spread ? "SpreadCycle (celui de la production)" : "StealthChop");
    Serial.println(" <<<");
    Serial.println("################################################");
    Serial.println("t_ms,phase,rpm,SG_RESULT,DIAG");

    Stats rampe, croisiere;
    tourner(true, rampe, croisiere);
    digitalWrite(EN_PIN, HIGH);
    delay(PAUSE_MS);

    Serial.println();
    Serial.print("--- BILAN ");
    Serial.print(spread ? "SpreadCycle" : "StealthChop");
    Serial.println(" ---");
    rampe.afficher("rampe    ");
    croisiere.afficher("croisiere");
    Serial.println("(la croisiere est la seule plage ou StallGuard est valide)");
    delay(PAUSE_MS);
  }
  digitalWrite(EN_PIN, HIGH);
  mesureFaite = true;
  Serial.println();
  Serial.println("### MESURE TERMINEE - driver coupe, plus rien ne tourne ###");
}
