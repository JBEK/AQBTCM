// Sketch pour contrôler les perceuses via PWM + relais fumée on/off

const int FUMEE_PIN = 9;  // ⚠️ Change si le relais est branché ailleurs

void setup() {
  Serial.begin(115200);
  pinMode(FUMEE_PIN, OUTPUT);
  digitalWrite(FUMEE_PIN, LOW); // Par défaut éteint
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');  // Lire jusqu'à \n
    cmd.trim();

    // Commande PWM pour perceuses : exemple "P5:120"
    if (cmd.startsWith("P")) {
      int sepIndex = cmd.indexOf(':');
      if (sepIndex != -1) {
        int pin = cmd.substring(1, sepIndex).toInt();
        int value = cmd.substring(sepIndex + 1).toInt();
        value = constrain(value, 0, 255);
        analogWrite(pin, value);
      }
    }

    // Commande allumer la fumée
    else if (cmd == "FUM_ON") {
      digitalWrite(FUMEE_PIN, HIGH);
    }

    // Commande éteindre la fumée
    else if (cmd == "FUM_OFF") {
      digitalWrite(FUMEE_PIN, LOW);
    }
  }
}
