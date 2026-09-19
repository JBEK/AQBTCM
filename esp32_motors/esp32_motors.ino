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
const uint8_t TMC_ADDR[3]  = {0, 1, 2};  // câblage MS1/MS2 réel sur site

TMC2209Stepper drivers[3] = {
  TMC2209Stepper(&Serial2, R_SENSE, TMC_ADDR[0]),
  TMC2209Stepper(&Serial2, R_SENSE, TMC_ADDR[1]),
  TMC2209Stepper(&Serial2, R_SENSE, TMC_ADDR[2]),
};

const unsigned long CYCLE_DUREE_MS = 18000;  // alternance horaire/antihoraire
const unsigned long ACCEL_MS = 500;
const unsigned long DECEL_MS = 500;
const int DELAI_MAX = 800;   // départ lent (µs entre demi-pas)
const int DELAI_MIN = 120;   // croisière rapide
const int RAMP_STEP = 4;

struct MotorState {
  bool active;
  bool dir;                     // true = horaire
  unsigned long cycleStartMs;
  unsigned long lastStepMicros;
  int delaiActuel;
  unsigned long pausedElapsedMs;
  bool wasActiveBeforePause;
};

MotorState motors[3];

void startMotorCycle(int id, bool fromCurrentDir = false) {
  MotorState &m = motors[id];
  if (!fromCurrentDir) m.dir = true;  // repart toujours horaire sur un START explicite
  digitalWrite(EN_PINS[id], LOW);  // réactive le driver (coupé à l'arrêt pour économiser les moteurs)
  digitalWrite(DIR_PINS[id], m.dir ? HIGH : LOW);
  m.cycleStartMs = millis();
  m.delaiActuel = DELAI_MAX;
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
    m.pausedElapsedMs = millis() - m.cycleStartMs;
    m.active = false;
    digitalWrite(EN_PINS[id], HIGH);
  }
}

void resumeMotorAfterHeartbeat(int id) {
  MotorState &m = motors[id];
  if (m.wasActiveBeforePause) {
    digitalWrite(EN_PINS[id], LOW);
    m.cycleStartMs = millis() - m.pausedElapsedMs;
    m.lastStepMicros = micros();
    m.active = true;
  }
}

void updateMotor(int id) {
  MotorState &m = motors[id];
  if (!m.active) return;

  unsigned long now = millis();
  unsigned long elapsed = now - m.cycleStartMs;

  if (elapsed >= CYCLE_DUREE_MS) {
    m.dir = !m.dir;
    digitalWrite(DIR_PINS[id], m.dir ? HIGH : LOW);
    m.cycleStartMs = now;
    m.delaiActuel = DELAI_MAX;
    elapsed = 0;
  }

  unsigned long nowMicros = micros();
  if (nowMicros - m.lastStepMicros >= (unsigned long)m.delaiActuel) {
    if (elapsed < ACCEL_MS && m.delaiActuel > DELAI_MIN) {
      m.delaiActuel = max(DELAI_MIN, m.delaiActuel - RAMP_STEP);
    } else if (CYCLE_DUREE_MS - elapsed < DECEL_MS && m.delaiActuel < DELAI_MAX) {
      m.delaiActuel = min(DELAI_MAX, m.delaiActuel + RAMP_STEP);
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
    int id = cmd.substring(1, sep).toInt();
    String action = cmd.substring(sep + 1);
    if (id < 0 || id > 2) {
      Serial.print("ERR_DRILL_ID:");
      Serial.println(id);
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
    motors[i] = {false, true, 0, 0, DELAI_MAX, 0, false};

    drivers[i].begin();
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
