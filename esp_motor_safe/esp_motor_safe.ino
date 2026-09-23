// ESP32_MOTORS — 3 perceuses sur moteurs pas-à-pas NEMA23 / TMC2209.
// Remplace uno_drill_pyserial.cpp et le sketch de test
// working_TMC2209_UART_FULLnm_SLOW (qui tournait en boucle bloquante et ne
// lisait jamais le port série pendant les 18s de rotation). Ici, chaque
// moteur est une petite machine à états mise à jour dans loop() sans jamais
// bloquer, sur le modèle des fonctions morse d'esp32_lights.ino : une
// commande série peut donc interrompre un moteur à tout moment, y compris en
// pleine accélération.

#include <Arduino.h>
#include <TMCStepper.h>

#define RXD2 21
#define TXD2 22
#define R_SENSE 0.11f
#define MICROSTEPS 8
#define PAS_PAR_TOUR 200        // NEMA23 1.8°

// câblage réel confirmé sur site
const uint8_t DIR_PINS[3]  = {19, 27, 33};
const uint8_t STEP_PINS[3] = {18, 26, 32};
const uint8_t EN_PINS[3]   = {5, 25, 14};
// adresses MS1/MS2 réellement mesurées sur chaque board (slots 1 et 2
// inversés par rapport à ce qu'on attendait, confirmé au multimètre) :
// Slot 0 -> adresse 0, Slot 1 -> adresse 2, Slot 2 -> adresse 1.
const uint8_t TMC_ADDR[3]  = {0, 2, 1};

TMC2209Stepper drivers[3] = {
  TMC2209Stepper(&Serial2, R_SENSE, TMC_ADDR[0]),
  TMC2209Stepper(&Serial2, R_SENSE, TMC_ADDR[1]),
  TMC2209Stepper(&Serial2, R_SENSE, TMC_ADDR[2]),
};

// Chaque machine entraîne un mécanisme différent (réduction différente),
// donc pas de valeur commune : durée de rotation et pause réglées par sens
// (index 0 = horaire, 1 = antihoraire — voir MotorState.dir), vitesse de
// croisière et forme de rampe réglées par machine.
//   0 = Machine 1 (polisseuse) : 3s/3s, pause 7s des 2 côtés
//   1 = Machine 2 (S23) : horaire 27s (=2x13s +1s), pause courte 3s, puis
//       antihoraire 26s (=2x13s), pause longue 7s avant de tout recommencer.
//       Rampe "douce" (celle testée avant qu'on trouve le vrai problème
//       d'alim/adresses) : démarrage très lent, montée en 5s, plutôt que la
//       rampe courte des 2 autres qui la faisait décrocher.
//   2 = Machine 3 : réglages identiques à Machine 2 (demandé explicitement)
const unsigned long CYCLE_MS[3][2] = {   // [machine][0=horaire,1=antihoraire]
  {3000, 3000},
  {27000, 26000},
  {27000, 26000},
};
const unsigned long PAUSE_MS[3][2] = {   // pause après CE sens, avant de repartir
  {7000, 7000},
  {3000, 7000},
  {3000, 7000},
};

// Vitesses exprimées en RPM (et non plus en µs de délai) : c'est ce qui
// détermine si le moteur tient ou décroche, donc autant le lire directement.
//   100 RPM -> 3.00 ms par pas complet : marge confortable
//   156 RPM -> 1.92 ms : ça grinçait déjà au banc
//   312 RPM -> 0.96 ms : l'ancien réglage, intenable en charge (le couple
//                        s'effondre sous la constante de temps L/R ~1.5 ms)
const float RPM_CROISIERE[3] = {100.0, 100.0, 100.0};
const float RPM_DEPART[3]    = {15.0, 15.0, 15.0};
const unsigned long ACCEL_MS[3]  = {800, 5000, 5000};
const unsigned long DECEL_MS[3]  = {800, 5000, 5000};

enum MotorPhase { RUNNING, PAUSED };

struct MotorState {
  bool active;
  bool dir;                     // true = horaire
  MotorPhase phase;
  unsigned long phaseStartMs;    // début de la phase courante (rotation ou pause)
  unsigned long lastStepMicros;
  unsigned long pausedElapsedMs; // pour la pause battement de cœur (voir plus bas)
  bool wasActiveBeforePause;
};

MotorState motors[3];

// Vitesse consigne à l'instant `elapsed` d'une rotation de durée `cycle` :
// montée à pente constante -> croisière -> descente à pente constante.
// L'ancienne version décrémentait un délai à chaque PAS, ce qui s'emballait :
// plus ça accélérait, plus les pas s'enchaînaient, donc plus ça accélérait
// (2 RPM/s au début, ~300 RPM/s sur la dernière seconde, pile là où le
// moteur a le moins de couple).
float rpmConsigne(int id, unsigned long elapsed, unsigned long cycle) {
  unsigned long accel = ACCEL_MS[id];
  unsigned long decel = DECEL_MS[id];
  // cycle trop court pour les deux rampes : on les réduit proportionnellement
  if (accel + decel > cycle) {
    accel = (unsigned long)((uint64_t)cycle * accel / (accel + decel));
    decel = cycle - accel;
  }
  float depart = RPM_DEPART[id];
  float ecart = RPM_CROISIERE[id] - depart;

  if (accel > 0 && elapsed < accel) {
    return depart + ecart * ((float)elapsed / accel);
  }
  if (decel > 0 && cycle - elapsed < decel) {
    return depart + ecart * ((float)(cycle - elapsed) / decel);
  }
  return RPM_CROISIERE[id];
}

// µs entre deux impulsions STEP pour une vitesse donnée
unsigned long delaiPourRPM(float rpm) {
  if (rpm < 1.0) rpm = 1.0;
  return (unsigned long)(1000000.0 / (rpm / 60.0 * PAS_PAR_TOUR * MICROSTEPS));
}

void startMotorCycle(int id, bool fromCurrentDir = false) {
  MotorState &m = motors[id];
  if (!fromCurrentDir) m.dir = true;  // repart toujours horaire sur un START explicite
  digitalWrite(EN_PINS[id], LOW);  // réactive le driver (coupé à l'arrêt pour économiser les moteurs)
  digitalWrite(DIR_PINS[id], m.dir ? HIGH : LOW);
  m.phase = RUNNING;
  m.phaseStartMs = millis();
  m.lastStepMicros = micros();
  m.active = true;
}

void stopMotor(int id) {
  motors[id].active = false;
  digitalWrite(EN_PINS[id], HIGH);  // désactive le driver : roue libre, pas de chauffe/conso à l'arrêt
}

void pauseMotorForHeartbeat(int id) {
  MotorState &m = motors[id];
  m.wasActiveBeforePause = m.active;
  if (m.active) {
    m.pausedElapsedMs = millis() - m.phaseStartMs;  // conserve l'avancement dans la phase en cours
    m.active = false;
    digitalWrite(EN_PINS[id], HIGH);
  }
}

void resumeMotorAfterHeartbeat(int id) {
  MotorState &m = motors[id];
  if (m.wasActiveBeforePause) {
    // EN reste actif (couple de maintien) aussi bien en RUNNING qu'en
    // PAUSED désormais (voir updateMotor) : on le réactive dans les deux cas.
    digitalWrite(EN_PINS[id], LOW);
    m.phaseStartMs = millis() - m.pausedElapsedMs;
    m.lastStepMicros = micros();
    m.active = true;
  }
}

void updateMotor(int id) {
  MotorState &m = motors[id];
  if (!m.active) return;

  unsigned long now = millis();
  unsigned long elapsed = now - m.phaseStartMs;
  // m.dir reflète le sens en cours (RUNNING) ou le sens qui vient de se
  // terminer (PAUSED, avant de basculer) : dans les deux cas c'est le bon
  // index pour lire la durée/pause de CE sens.
  int dirIdx = m.dir ? 0 : 1;

  if (m.phase == PAUSED) {
    if (elapsed >= PAUSE_MS[id][dirIdx]) {
      // fin de la pause : repart dans l'autre sens
      m.dir = !m.dir;
      digitalWrite(DIR_PINS[id], m.dir ? HIGH : LOW);
      digitalWrite(EN_PINS[id], LOW);
      m.phase = RUNNING;
      m.phaseStartMs = now;
      m.lastStepMicros = micros();
    }
    return;
  }

  // phase RUNNING
  if (elapsed >= CYCLE_MS[id][dirIdx]) {
    // fin de la rotation dans ce sens : pause. Le driver reste ACTIF (couple
    // de maintien) pendant la pause plutôt que désactivé : en roue libre, le
    // rotor peut légèrement dériver, et le réveil brutal au sens suivant
    // "recale" le rotor d'un coup — c'est ce qui produisait le clac entendu
    // sur tous les moteurs à chaque changement de sens, indépendamment du
    // mode de hachage.
    m.phase = PAUSED;
    m.phaseStartMs = now;
    return;
  }

  float rpm = rpmConsigne(id, elapsed, CYCLE_MS[id][dirIdx]);
  unsigned long delai = delaiPourRPM(rpm);
  unsigned long nowMicros = micros();
  if (nowMicros - m.lastStepMicros >= delai) {
    digitalWrite(STEP_PINS[id], HIGH);
    delayMicroseconds(2);  // largeur d'impulsion STEP minimale, négligeable
    digitalWrite(STEP_PINS[id], LOW);
    m.lastStepMicros = nowMicros;
  }
}

String serialBuffer = "";

void handleCommand(const String& cmd) {
  if (cmd == "ID?") {
    Serial.println("AQBTCM_MOTORS");

  } else if (cmd == "D:ALL:START") {
    for (int i = 0; i < 3; i++) startMotorCycle(i);
  } else if (cmd == "D:ALL:STOP") {
    for (int i = 0; i < 3; i++) stopMotor(i);

  } else if (cmd.startsWith("D") && cmd.indexOf(':') != -1) {
    int sep = cmd.indexOf(':');
    // numéro 1/2/3 côté protocole (même numéro que le bouton "Perceuse N" du
    // GUI et que le câblage réel) ; converti en index de tableau 0/1/2 ici.
    int num = cmd.substring(1, sep).toInt();
    int id = num - 1;
    String action = cmd.substring(sep + 1);
    if (num < 1 || num > 3) {
      Serial.print("ERR_DRILL_ID:");
      Serial.println(num);
    } else if (action == "START") {
      startMotorCycle(id);
    } else if (action == "STOP") {
      stopMotor(id);
    } else {
      Serial.println("ERR_FORMAT_D");
    }

  } else if (cmd == "H:START") {
    for (int i = 0; i < 3; i++) pauseMotorForHeartbeat(i);
  } else if (cmd == "H:STOP") {
    for (int i = 0; i < 3; i++) resumeMotorAfterHeartbeat(i);

  } else {
    Serial.print("ERR_UNKNOWN_CMD:");
    Serial.println(cmd);
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);

  for (int i = 0; i < 3; i++) {
    pinMode(STEP_PINS[i], OUTPUT);
    pinMode(DIR_PINS[i], OUTPUT);
    pinMode(EN_PINS[i], OUTPUT);
    digitalWrite(EN_PINS[i], HIGH);  // désactivé par défaut : aucun moteur ne tourne au boot
    motors[i] = {false, true, RUNNING, 0, 0, 0, false};

    drivers[i].begin();
    uint8_t statut = drivers[i].test_connection();
    Serial.print("Moteur "); Serial.print(i); Serial.print(" test_connection() = "); Serial.print(statut);
    Serial.println(statut == 0 ? "  -> OK, driver present" : "  -> ECHEC, pas de reponse UART");
    drivers[i].toff(5);
    // 1100 mA RMS ~= 1.55 A crête = courant nominal du moteur (1.5 A).
    // L'ancien 1300 RMS faisait 1.84 A crête, 22% au-dessus : ça chauffait
    // le moteur sans rien apporter (à haute vitesse le facteur limitant est
    // la tension/inductance, pas le courant réglé).
    drivers[i].rms_current(1100);
    drivers[i].microsteps(MICROSTEPS);
    drivers[i].en_spreadCycle(true);  // couple garanti quelles que soient charge et vitesse
    // mode 2 des 3 testés (SpreadCycle + interpolation 256 micropas interne) :
    // intpol ne coûte aucun couple (aucune impulsion supplémentaire à
    // envoyer), juste une forme d'onde plus douce - donc au moins aussi bon
    // que le mode 1 pour le couple, en plus lisse.
    drivers[i].intpol(true);
  }

  Serial.println("AQBTCM_MOTORS prêt.");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      serialBuffer.trim();
      if (serialBuffer.length() > 0) handleCommand(serialBuffer);
      serialBuffer = "";
    } else if (serialBuffer.length() < 60) {
      serialBuffer += c;
    }
  }

  for (int i = 0; i < 3; i++) updateMotor(i);
}
