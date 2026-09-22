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

// Chaque perceuse entraîne un mécanisme différent (réduction différente),
// donc pas de valeur commune : durée de rotation par sens, pause entre les
// deux sens, et vitesse de croisière (µs entre demi-pas, plus petit = plus
// rapide), réglés indépendamment pour chacune.
//   0 = polisseuse : 3s/3s, pause 7s
//   1 = perceuse S23 : 7s/7s, pause 7s — rampe "douce" (celle testée avant
//       qu'on trouve le vrai problème d'alim/adresses) : démarrage très
//       lent, montée en 5s, plutôt que la rampe courte des 2 autres qui la
//       faisait décrocher
//   2 = à régler (valeurs provisoires en attendant, identiques à la 1)
const unsigned long CYCLE_MS[3]  = {3000, 13000, 3000};  // perceuse 2 : 5s montée + 3s pleine vitesse + 5s descente
const unsigned long PAUSE_MS[3]  = {7000, 7000, 7000};
const int CRUISE_DELAI[3]        = {120, 120, 120};
const unsigned long ACCEL_MS[3]  = {500, 5000, 500};
const unsigned long DECEL_MS[3]  = {500, 5000, 500};
const int DELAI_MAX[3]           = {800, 4000, 800};  // départ lent (µs entre demi-pas)
const int RAMP_STEP[3]           = {4, 2, 4};

enum MotorPhase { RUNNING, PAUSED };

struct MotorState {
  bool active;
  bool dir;                     // true = horaire
  MotorPhase phase;
  unsigned long phaseStartMs;    // début de la phase courante (rotation ou pause)
  unsigned long lastStepMicros;
  int delaiActuel;
  unsigned long pausedElapsedMs; // pour la pause battement de cœur (voir plus bas)
  bool wasActiveBeforePause;
};

MotorState motors[3];

void startMotorCycle(int id, bool fromCurrentDir = false) {
  MotorState &m = motors[id];
  if (!fromCurrentDir) m.dir = true;  // repart toujours horaire sur un START explicite
  digitalWrite(EN_PINS[id], LOW);  // réactive le driver (coupé à l'arrêt pour économiser les moteurs)
  digitalWrite(DIR_PINS[id], m.dir ? HIGH : LOW);
  m.phase = RUNNING;
  m.phaseStartMs = millis();
  m.delaiActuel = DELAI_MAX[id];
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
    if (m.phase == RUNNING) digitalWrite(EN_PINS[id], LOW);
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

  if (m.phase == PAUSED) {
    if (elapsed >= PAUSE_MS[id]) {
      // fin de la pause : repart dans l'autre sens
      m.dir = !m.dir;
      digitalWrite(DIR_PINS[id], m.dir ? HIGH : LOW);
      digitalWrite(EN_PINS[id], LOW);
      m.phase = RUNNING;
      m.phaseStartMs = now;
      m.delaiActuel = DELAI_MAX[id];
      m.lastStepMicros = micros();
    }
    return;
  }

  // phase RUNNING
  if (elapsed >= CYCLE_MS[id]) {
    // fin de la rotation dans ce sens : pause, driver désactivé (roue libre)
    m.phase = PAUSED;
    m.phaseStartMs = now;
    digitalWrite(EN_PINS[id], HIGH);
    return;
  }

  unsigned long nowMicros = micros();
  if (nowMicros - m.lastStepMicros >= (unsigned long)m.delaiActuel) {
    if (elapsed < ACCEL_MS[id] && m.delaiActuel > CRUISE_DELAI[id]) {
      m.delaiActuel = max(CRUISE_DELAI[id], m.delaiActuel - RAMP_STEP[id]);
    } else if (CYCLE_MS[id] - elapsed < DECEL_MS[id] && m.delaiActuel < DELAI_MAX[id]) {
      m.delaiActuel = min(DELAI_MAX[id], m.delaiActuel + RAMP_STEP[id]);
    }
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
    motors[i] = {false, true, RUNNING, 0, 0, DELAI_MAX[i], 0, false};

    drivers[i].begin();
    uint8_t statut = drivers[i].test_connection();
    Serial.print("Moteur "); Serial.print(i); Serial.print(" test_connection() = "); Serial.print(statut);
    Serial.println(statut == 0 ? "  -> OK, driver present" : "  -> ECHEC, pas de reponse UART");
    drivers[i].toff(5);
    drivers[i].rms_current(1300);
    drivers[i].microsteps(8);
    drivers[i].en_spreadCycle(true);
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
