// ESP32_LIGHTS — bandeaux LED (PCA9685 + MOSFETs) + machine à fumée.
// Remplace mega_light_pyserial.ino : même logique morse (machine à états
// non-bloquante millis()), mais pilote un PCA9685 au lieu d'analogWrite
// direct. Reprend FUM_ON/FUM_OFF de l'ancien firmware Uno.

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

#define PWM_FREQ_HZ 1000   // validé sans scintillement
#define FUM_PIN 4

// Chaque groupe = 4 canaux "tubes" + 1 canal "ALL" (bandeau continu du même
// luminaire), qui suit le groupe comme un 5e tube.
const uint8_t channelsA[] = {0, 1, 2, 3, 4};
const uint8_t channelsB[] = {5, 6, 7, 8, 9};
const uint8_t channelsC[] = {10, 11, 12, 13, 14};
const int NUM_CH_PER_GROUP = 5;

enum OpMode { NONE, MORSE, HEARTBEAT, MANUAL_PWM };
OpMode currentOpMode = NONE;

// Durées morse en ms
const int dotDuration = 200;
const int dashDuration = 600;
const int intraCharPause = 200;
const int interCharPause = 600;
const int interWordPause = 1400;

String soliste = "";
String phrase = "";
String choeurMot = "";
String choeurGroupes[2];

bool morseEnCours = false;
bool okEnvoye = true;

const uint8_t* solistePins = nullptr;
String solisteCode = "";
int indexSignalSoliste = 0;
bool solisteLedAllume = false;
unsigned long solisteTimer = 0;

const uint8_t* choeurPins1 = nullptr;
const uint8_t* choeurPins2 = nullptr;
String choeurCode = "";
int indexSignalChoeur = 0;
bool choeurLedAllume = false;
unsigned long choeurTimer = 0;

String serialBuffer = "";

// ---- PWM ----
void setChannelPWM(uint8_t channel, int brightness255) {
  brightness255 = constrain(brightness255, 0, 255);
  uint16_t duty = map(brightness255, 0, 255, 0, 4095);
  pwm.setPWM(channel, 0, duty);
}

void setGroupPWM(const uint8_t* channels, int brightness255) {
  for (int i = 0; i < NUM_CH_PER_GROUP; i++) {
    setChannelPWM(channels[i], brightness255);
  }
}

const uint8_t* groupChannels(const String& g) {
  if (g == "A") return channelsA;
  if (g == "B") return channelsB;
  return channelsC;
}

bool channelIsManaged(int channel) {
  for (int i = 0; i < NUM_CH_PER_GROUP; i++) {
    if (channelsA[i] == channel || channelsB[i] == channel || channelsC[i] == channel) return true;
  }
  return false;
}

// ---- Morse ----
String lettreToMorse(char c) {
  c = toupper(c);
  switch (c) {
    case 'A': return ".-";
    case 'B': return "-...";
    case 'C': return "-.-.";
    case 'D': return "-..";
    case 'E': return ".";
    case 'F': return "..-.";
    case 'G': return "--.";
    case 'H': return "....";
    case 'I': return "..";
    case 'J': return ".---";
    case 'K': return "-.-";
    case 'L': return ".-..";
    case 'M': return "--";
    case 'N': return "-.";
    case 'O': return "---";
    case 'P': return ".--.";
    case 'Q': return "--.-";
    case 'R': return ".-.";
    case 'S': return "...";
    case 'T': return "-";
    case 'U': return "..-";
    case 'V': return "...-";
    case 'W': return ".--";
    case 'X': return "-..-";
    case 'Y': return "-.--";
    case 'Z': return "--..";
    case '0': return "-----";
    case '1': return ".----";
    case '2': return "..---";
    case '3': return "...--";
    case '4': return "....-";
    case '5': return ".....";
    case '6': return "-....";
    case '7': return "--...";
    case '8': return "---..";
    case '9': return "----.";
    case ' ': return " ";
    default: return "";
  }
}

String phraseToMorse(const String& texte) {
  String resultat = "";
  for (unsigned int i = 0; i < texte.length(); i++) {
    String morse = lettreToMorse(texte.charAt(i));
    if (morse == "") continue;
    resultat += (morse == " ") ? " " : (morse + " ");
  }
  return resultat;
}

void avancerMorseSoliste(const uint8_t* channels, const String& code, int& indexSignal, bool& ledAllume, unsigned long& timer) {
  if (code.length() == 0 || channels == nullptr || indexSignal >= (int)code.length()) return;
  unsigned long now = millis();
  char c = code.charAt(indexSignal);

  if (!ledAllume) {
    if (c == '.' || c == '-') {
      for (int bri = 0; bri <= 255; bri += 51) {
        setGroupPWM(channels, bri);
        delay(15);
      }
      timer = now;
      ledAllume = true;
    } else if (c == ' ') {
      unsigned long pauseDuration = (code.charAt(indexSignal + 1) == ' ' || indexSignal + 1 >= (int)code.length()) ? interWordPause : interCharPause;
      if (now - timer >= pauseDuration) {
        indexSignal++;
        timer = now;
      }
    } else {
      indexSignal++;
    }
  } else {
    unsigned long duree = (c == '.') ? dotDuration : dashDuration;
    if (now - timer >= duree) {
      for (int bri = 255; bri >= 0; bri -= 51) {
        setGroupPWM(channels, bri);
        delay(15);
      }
      ledAllume = false;
      indexSignal++;
      timer = now;
    }
  }
}

void avancerMorseChoeurs(const uint8_t* channels1, const uint8_t* channels2, const String& code, int& indexSignal, bool& ledAllume, unsigned long& timer) {
  if (code.length() == 0 || channels1 == nullptr || channels2 == nullptr || indexSignal >= (int)code.length()) return;
  unsigned long now = millis();
  char c = code.charAt(indexSignal);

  if (!ledAllume) {
    if (c == '.' || c == '-') {
      for (int bri = 20; bri <= 120; bri += 10) {
        setGroupPWM(channels1, bri);
        setGroupPWM(channels2, bri);
        delay(50);
      }
      timer = now;
      ledAllume = true;
    } else if (c == ' ') {
      unsigned long pauseDuration = (code.charAt(indexSignal + 1) == ' ' || indexSignal + 1 >= (int)code.length()) ? interWordPause * 2 : interCharPause * 2;
      if (now - timer >= pauseDuration) {
        indexSignal++;
        timer = now;
      }
    } else {
      indexSignal++;
    }
  } else {
    unsigned long duree = (c == '.') ? dotDuration * 3 : dashDuration * 3;
    if (now - timer >= duree) {
      for (int bri = 120; bri >= 20; bri -= 10) {
        setGroupPWM(channels1, bri);
        setGroupPWM(channels2, bri);
        delay(50);
      }
      ledAllume = false;
      indexSignal++;
      timer = now;
    }
  }
}

void resetAllModes() {
  morseEnCours = false;
  setGroupPWM(channelsA, 0);
  setGroupPWM(channelsB, 0);
  setGroupPWM(channelsC, 0);
}

void declamer(String solisteGroupe, String phraseRecue, String motChoeurRecue) {
  String groupes[3] = {"A", "B", "C"};
  int idxSoliste = 0;
  for (int i = 0; i < 3; i++) if (groupes[i] == solisteGroupe) idxSoliste = i;
  int idxChoeur1 = (idxSoliste + 1) % 3;
  int idxChoeur2 = (idxSoliste + 2) % 3;

  choeurGroupes[0] = groupes[idxChoeur1];
  choeurGroupes[1] = groupes[idxChoeur2];
  soliste = solisteGroupe;
  phrase = phraseRecue;
  choeurMot = motChoeurRecue;

  solistePins = groupChannels(soliste);
  choeurPins1 = groupChannels(choeurGroupes[0]);
  choeurPins2 = groupChannels(choeurGroupes[1]);

  solisteCode = phraseToMorse(phrase);
  choeurCode = phraseToMorse(choeurMot);

  indexSignalSoliste = 0;
  indexSignalChoeur = 0;
  solisteLedAllume = false;
  choeurLedAllume = false;
  solisteTimer = millis();
  choeurTimer = millis();
  morseEnCours = true;
  okEnvoye = false;
}

// ---- Setup / loop ----
void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(PWM_FREQ_HZ);

  pinMode(FUM_PIN, OUTPUT);
  digitalWrite(FUM_PIN, LOW);

  resetAllModes();
  currentOpMode = NONE;
  okEnvoye = true;

  Serial.println("AQBTCM_LIGHTS prêt.");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      serialBuffer.trim();

      if (serialBuffer == "ID?") {
        Serial.println("AQBTCM_LIGHTS");

      } else if (serialBuffer.startsWith("M:")) {
        resetAllModes();
        currentOpMode = MORSE;
        int pos1 = serialBuffer.indexOf(':');
        int pos2 = serialBuffer.indexOf('|', pos1 + 1);
        int pos3 = serialBuffer.indexOf('|', pos2 + 1);
        int posStar1 = serialBuffer.indexOf('*', pos3 + 1);
        int posStar2 = serialBuffer.indexOf('*', posStar1 + 1);
        if (pos1 != -1 && pos2 != -1 && pos3 != -1 && posStar1 != -1 && posStar2 != -1) {
          declamer(
            serialBuffer.substring(pos1 + 1, pos2),
            serialBuffer.substring(pos2 + 1, pos3),
            serialBuffer.substring(posStar1 + 1, posStar2)
          );
        } else {
          Serial.println("ERR_FORMAT_M");
        }

      } else if (serialBuffer.startsWith("P")) {
        if (currentOpMode == MORSE || currentOpMode == HEARTBEAT) resetAllModes();
        currentOpMode = MANUAL_PWM;
        int sep = serialBuffer.indexOf(':');
        if (sep > 0 && sep < (int)serialBuffer.length() - 1) {
          int channel = serialBuffer.substring(1, sep).toInt();
          int val = constrain(serialBuffer.substring(sep + 1).toInt(), 0, 255);
          if (channelIsManaged(channel)) {
            setChannelPWM(channel, val);
            Serial.println("OK");
          } else {
            Serial.print("ERR_CH_UNMANAGED:");
            Serial.println(channel);
          }
        } else {
          Serial.println("ERR_FORMAT_P");
        }

      } else if (serialBuffer.startsWith("H:")) {
        String arg = serialBuffer.substring(2);
        if (arg == "STOP") {
          resetAllModes();
          currentOpMode = NONE;
        } else {
          if (currentOpMode != HEARTBEAT) resetAllModes();
          currentOpMode = HEARTBEAT;
          int val = constrain(arg.toInt(), 0, 255);
          setGroupPWM(channelsA, val);
          setGroupPWM(channelsB, val);
          setGroupPWM(channelsC, val);
        }

      } else if (serialBuffer == "FUM_ON") {
        digitalWrite(FUM_PIN, HIGH);
      } else if (serialBuffer == "FUM_OFF") {
        digitalWrite(FUM_PIN, LOW);

      } else {
        Serial.print("ERR_UNKNOWN_CMD:");
        Serial.println(serialBuffer);
      }
      serialBuffer = "";
    } else if (serialBuffer.length() < 100) {
      serialBuffer += c;
    }
  }

  if (morseEnCours) {
    avancerMorseSoliste(solistePins, solisteCode, indexSignalSoliste, solisteLedAllume, solisteTimer);
    avancerMorseChoeurs(choeurPins1, choeurPins2, choeurCode, indexSignalChoeur, choeurLedAllume, choeurTimer);

    bool solisteFini = (solisteCode.length() == 0 || indexSignalSoliste >= (int)solisteCode.length());
    bool choeurFini = (choeurCode.length() == 0 || indexSignalChoeur >= (int)choeurCode.length());

    if (solisteFini && choeurFini) {
      morseEnCours = false;
      if (currentOpMode == MORSE) currentOpMode = NONE;
      if (!okEnvoye) {
        Serial.println("OK");
        okEnvoye = true;
      }
    }
  }
}
