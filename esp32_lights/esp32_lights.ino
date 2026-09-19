// ESP32_LIGHTS — bandeaux LED (PCA9685 + MOSFETs) + machine à fumée.
//
// Morse soliste + chœurs, entièrement NON-BLOQUANT : aucun delay() dans
// loop(). Les fondus sont calculés à partir de millis() à chaque tour, donc
// le port série est lu en continu et le soliste n'est jamais figé par un
// fondu de chœur.
//
// Chœurs : le soliste épelle toute la phrase. Quand il arrive sur un mot
// marqué *comme ça*, les deux autres luminaires se mettent à réciter ce mot
// en boucle, doucement, et continuent PENDANT LES PHRASES SUIVANTES jusqu'à
// ce qu'un nouveau mot marqué arrive (ils basculent alors sur ce mot).

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

#define PWM_FREQ_HZ 1000   // validé sans scintillement
#define FUM_PIN 4
#define OE_PIN 5           // Output Enable du PCA9685 (actif bas), coupure matérielle instantanée

// Chaque groupe = 4 canaux "tubes" WW individuels. Le CW (blanc froid) de
// chaque luminaire est câblé à part : les 4 pattes CW des tubes d'un même
// luminaire sont bundlées ensemble sur 1 seul canal MOSFET (channelsCW) —
// accessible seulement en manuel (P<canal>:<valeur>), jamais piloté par le
// morse ni le heartbeat, pour ne pas casser l'ambiance chaude voulue.
const uint8_t channelsA[] = {0, 1, 2, 3};
const uint8_t channelsB[] = {4, 5, 6, 7};
const uint8_t channelsC[] = {8, 9, 10, 11};
const int NUM_CH_PER_GROUP = 4;

const uint8_t channelsCW[] = {12, 13, 14};  // CW luminaire 1, 2, 3

enum OpMode { NONE, MORSE, HEARTBEAT, MANUAL_PWM };
OpMode currentOpMode = NONE;

// ---- Réglages morse (ms, luminosité 0-255) ----
// Soliste : fondu rapide, plein régime.
const int SOLISTE_LO = 0;
const int SOLISTE_HI = 255;
const int SOLISTE_FADE_MS = 90;
const unsigned long SOLISTE_DOT_MS = 200;
const unsigned long SOLISTE_DASH_MS = 600;
const unsigned long SOLISTE_CHAR_PAUSE_MS = 600;
const unsigned long SOLISTE_WORD_PAUSE_MS = 1400;

// Chœurs : fondu lent, lumière douce (jamais au maximum), récitent en boucle.
const int CHOEUR_LO = 20;
const int CHOEUR_HI = 120;
const int CHOEUR_FADE_MS = 550;
const unsigned long CHOEUR_DOT_MS = 600;
const unsigned long CHOEUR_DASH_MS = 1800;
const unsigned long CHOEUR_CHAR_PAUSE_MS = 1200;
const unsigned long CHOEUR_WORD_PAUSE_MS = 2800;

// ---- Une "voix" morse : machine à états à base de millis() ----
enum VoicePhase { V_IDLE, V_SYMBOL, V_PAUSE, V_DONE };

struct MorseVoice {
  String code;               // ex ".- -... " : chaque lettre suivie d'un espace
  int index;
  VoicePhase phase;
  unsigned long phaseStart;
  unsigned long phaseDur;
  int level;                 // luminosité courante, recalculée à chaque tour
  int lo, hi, fadeMs;
  unsigned long dotMs, dashMs, charPauseMs, wordPauseMs;
  bool loop;                 // le chœur reboucle sur son mot
};

void voiceConfig(MorseVoice& v, int lo, int hi, int fadeMs,
                 unsigned long dot, unsigned long dash,
                 unsigned long charPause, unsigned long wordPause, bool loop) {
  v.lo = lo; v.hi = hi; v.fadeMs = fadeMs;
  v.dotMs = dot; v.dashMs = dash;
  v.charPauseMs = charPause; v.wordPauseMs = wordPause;
  v.loop = loop;
  v.code = "";
  v.index = 0;
  v.phase = V_DONE;
  v.level = lo;
}

void voiceStart(MorseVoice& v, const String& code) {
  v.code = code;
  v.index = 0;
  v.phase = V_IDLE;
  v.level = v.lo;
}

void voiceUpdate(MorseVoice& v, unsigned long now) {
  int len = v.code.length();

  // Choisit l'élément suivant (symbole ou pause). Le garde-fou évite de
  // tourner à vide si le code ne contient rien d'exploitable.
  for (int guard = 0; v.phase == V_IDLE && guard < 8; guard++) {
    if (v.index >= len) {
      if (v.loop && len > 0) { v.index = 0; continue; }
      v.phase = V_DONE;
      break;
    }
    char c = v.code.charAt(v.index);
    if (c == '.' || c == '-') {
      v.phase = V_SYMBOL;
      v.phaseStart = now;
      v.phaseDur = (c == '.') ? v.dotMs : v.dashMs;
    } else if (c == ' ') {
      bool finDeMot = (v.index + 1 >= len) || v.code.charAt(v.index + 1) == ' ';
      v.phase = V_PAUSE;
      v.phaseStart = now;
      v.phaseDur = finDeMot ? v.wordPauseMs : v.charPauseMs;
    } else {
      v.index++;
    }
  }

  if (v.phase == V_SYMBOL) {
    unsigned long t = now - v.phaseStart;
    if (t >= v.phaseDur + (unsigned long)v.fadeMs) {
      v.phase = V_IDLE;
      v.index++;
      v.level = v.lo;
    } else if (t < (unsigned long)v.fadeMs) {
      v.level = v.lo + (int)((long)(v.hi - v.lo) * (long)t / v.fadeMs);       // fondu entrant
    } else if (t < v.phaseDur) {
      v.level = v.hi;                                                          // plein
    } else {
      v.level = v.hi - (int)((long)(v.hi - v.lo) * (long)(t - v.phaseDur) / v.fadeMs);  // fondu sortant
    }
  } else if (v.phase == V_PAUSE) {
    v.level = v.lo;
    if (now - v.phaseStart >= v.phaseDur) {
      v.phase = V_IDLE;
      v.index++;
    }
  } else {
    v.level = v.lo;
  }
}

// ---- État de la déclamation ----
MorseVoice soliste;
MorseVoice choeur;

const uint8_t* solistePins = nullptr;
const uint8_t* choeurPins1 = nullptr;
const uint8_t* choeurPins2 = nullptr;

bool solisteEnCours = false;   // une phrase est en train d'être épelée
bool okEnvoye = true;          // "OK" renvoyé quand le soliste a fini sa phrase

bool choeurActif = false;      // les chœurs récitent un mot (persiste d'une phrase à l'autre)
bool choeurSwapEnAttente = false;
String choeurEnAttente = "";

// Mots de chœur d'une phrase : déclenchés quand le soliste atteint leur position
#define MAX_TRIGGERS 8
int triggerIndex[MAX_TRIGGERS];
String triggerCode[MAX_TRIGGERS];
bool triggerFired[MAX_TRIGGERS];
int triggerCount = 0;

int lastSolisteLevel = -1;
int lastChoeurLevel = -1;

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

bool channelIsManaged(int channel) {
  for (int i = 0; i < NUM_CH_PER_GROUP; i++) {
    if (channelsA[i] == channel || channelsB[i] == channel || channelsC[i] == channel) return true;
  }
  for (int i = 0; i < 3; i++) {
    if (channelsCW[i] == channel) return true;  // CW en manuel uniquement (voir P<canal>:<valeur>)
  }
  return false;
}

// ---- Morse ----
String lettreToMorse(char c) {
  if ((unsigned char)c > 127) return "";  // octets UTF-8 (accents, apostrophes typographiques) ignorés
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

// Applique un niveau à un ou deux groupes, seulement s'il a changé (évite du
// trafic I2C inutile pendant les paliers).
void appliquerNiveau(const uint8_t* g1, const uint8_t* g2, int level, int& last) {
  if (level == last) return;
  if (g1 != nullptr) setGroupPWM(g1, level);
  if (g2 != nullptr) setGroupPWM(g2, level);
  last = level;
}

void resetAllModes() {
  solisteEnCours = false;
  choeurActif = false;
  choeurSwapEnAttente = false;
  triggerCount = 0;
  setGroupPWM(channelsA, 0);
  setGroupPWM(channelsB, 0);
  setGroupPWM(channelsC, 0);
  lastSolisteLevel = -1;
  lastChoeurLevel = -1;
}

// Assigne soliste + 2 chœurs. Retourne false si le groupe est inconnu.
bool preparerGroupes(const String& groupe) {
  int idx = -1;
  if (groupe == "A") idx = 0;
  else if (groupe == "B") idx = 1;
  else if (groupe == "C") idx = 2;
  if (idx < 0) return false;

  const uint8_t* groupes[3] = {channelsA, channelsB, channelsC};
  const uint8_t* s = groupes[idx];
  const uint8_t* c1 = groupes[(idx + 1) % 3];
  const uint8_t* c2 = groupes[(idx + 2) % 3];

  if (s != solistePins || c1 != choeurPins1 || c2 != choeurPins2) {
    // les rôles changent : on éteint tout, chaque groupe sera réécrit ensuite
    setGroupPWM(channelsA, 0);
    setGroupPWM(channelsB, 0);
    setGroupPWM(channelsC, 0);
    lastSolisteLevel = -1;
    lastChoeurLevel = -1;
  }
  solistePins = s;
  choeurPins1 = c1;
  choeurPins2 = c2;
  return true;
}

void lancerSoliste(const String& code) {
  voiceStart(soliste, code);
  solisteEnCours = true;
  okEnvoye = false;
}

// Nouveau format : "phrase avec *mots* marqués". Le morse du soliste est la
// phrase entière ; chaque mot marqué devient un déclencheur de chœur placé à
// l'endroit du morse où le mot commence.
void declamerTexte(const String& texte) {
  String code = "";
  triggerCount = 0;
  bool dansEtoile = false;
  String mot = "";
  int debutMot = 0;

  for (unsigned int i = 0; i < texte.length(); i++) {
    char ch = texte.charAt(i);
    if (ch == '*') {
      if (!dansEtoile) {
        dansEtoile = true;
        mot = "";
        debutMot = code.length();
      } else {
        dansEtoile = false;
        String motCode = phraseToMorse(mot);
        if (motCode.length() > 0 && triggerCount < MAX_TRIGGERS) {
          triggerIndex[triggerCount] = debutMot;
          triggerCode[triggerCount] = motCode;
          triggerFired[triggerCount] = false;
          triggerCount++;
        }
      }
      continue;
    }
    String m = lettreToMorse(ch);
    if (m == "") continue;
    code += (m == " ") ? " " : (m + " ");
    if (dansEtoile) mot += ch;
  }
  lancerSoliste(code);
}

// Ancien format "M:<soliste>|<phrase>|*<mot>*" : le chœur récite son mot dès
// le début de la phrase.
void declamerAncien(const String& phrase, const String& motChoeur) {
  triggerCount = 0;
  String motCode = phraseToMorse(motChoeur);
  if (motCode.length() > 0) {
    triggerIndex[0] = 0;
    triggerCode[0] = motCode;
    triggerFired[0] = false;
    triggerCount = 1;
  }
  lancerSoliste(phraseToMorse(phrase));
}

// Avance soliste + chœurs d'un cran (appelé à chaque tour de loop()).
void avancerMorse() {
  unsigned long now = millis();

  if (solisteEnCours) {
    voiceUpdate(soliste, now);

    // le soliste arrive sur un mot marqué : les chœurs vont le réciter
    for (int i = 0; i < triggerCount; i++) {
      if (!triggerFired[i] && soliste.index >= triggerIndex[i]) {
        triggerFired[i] = true;
        choeurEnAttente = triggerCode[i];
        choeurSwapEnAttente = true;
      }
    }

    appliquerNiveau(solistePins, nullptr, soliste.level, lastSolisteLevel);

    if (soliste.phase == V_DONE) {
      solisteEnCours = false;
      if (!okEnvoye) {
        Serial.println("OK");
        okEnvoye = true;
      }
    }
  }

  // Changement de mot de chœur : on attend la fin du symbole en cours pour
  // ne pas couper un fondu net.
  if (choeurSwapEnAttente && (!choeurActif || choeur.phase != V_SYMBOL)) {
    voiceStart(choeur, choeurEnAttente);
    choeurActif = true;
    choeurSwapEnAttente = false;
  }

  if (choeurActif) {
    voiceUpdate(choeur, now);
    appliquerNiveau(choeurPins1, choeurPins2, choeur.level, lastChoeurLevel);
  }
}

// ---- Commande M ----
// Nouveau format : M:<soliste>|<phrase avec *mots* marqués>
// Ancien format  : M:<soliste>|<phrase>|*<mot>*
void traiterCommandeM() {
  // M enchaîné à un autre M : on garde les chœurs en cours (ils continuent
  // pendant la phrase suivante). Depuis un autre mode : on repart propre.
  if (currentOpMode != MORSE) resetAllModes();
  currentOpMode = MORSE;

  int pos1 = serialBuffer.indexOf(':');
  int pos2 = serialBuffer.indexOf('|', pos1 + 1);
  if (pos1 == -1 || pos2 == -1) {
    Serial.println("ERR_FORMAT_M");
    return;
  }
  if (!preparerGroupes(serialBuffer.substring(pos1 + 1, pos2))) {
    Serial.println("ERR_FORMAT_M");
    return;
  }

  int pos3 = serialBuffer.indexOf('|', pos2 + 1);
  if (pos3 == -1) {
    declamerTexte(serialBuffer.substring(pos2 + 1));
  } else {
    int etoile1 = serialBuffer.indexOf('*', pos3 + 1);
    int etoile2 = serialBuffer.indexOf('*', etoile1 + 1);
    if (etoile1 == -1 || etoile2 == -1) {
      Serial.println("ERR_FORMAT_M");
      return;
    }
    declamerAncien(serialBuffer.substring(pos2 + 1, pos3),
                   serialBuffer.substring(etoile1 + 1, etoile2));
  }
}

// ---- Setup / loop ----
void setup() {
  Serial.setRxBufferSize(1024);  // phrases longues : doit précéder Serial.begin()
  Serial.begin(115200);
  delay(1000);

  pinMode(OE_PIN, OUTPUT);
  digitalWrite(OE_PIN, HIGH);  // sorties coupées pendant l'init, évite un flash au boot

  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(PWM_FREQ_HZ);
  Wire.setClock(400000);       // I2C rapide : les fondus mettent à jour plusieurs canaux à chaque tour

  pinMode(FUM_PIN, OUTPUT);
  digitalWrite(FUM_PIN, LOW);

  voiceConfig(soliste, SOLISTE_LO, SOLISTE_HI, SOLISTE_FADE_MS,
              SOLISTE_DOT_MS, SOLISTE_DASH_MS,
              SOLISTE_CHAR_PAUSE_MS, SOLISTE_WORD_PAUSE_MS, false);
  voiceConfig(choeur, CHOEUR_LO, CHOEUR_HI, CHOEUR_FADE_MS,
              CHOEUR_DOT_MS, CHOEUR_DASH_MS,
              CHOEUR_CHAR_PAUSE_MS, CHOEUR_WORD_PAUSE_MS, true);

  resetAllModes();
  currentOpMode = NONE;
  okEnvoye = true;

  digitalWrite(OE_PIN, LOW);  // tout est à zéro, on peut activer les sorties

  Serial.println("AQBTCM_LIGHTS prêt.");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      serialBuffer.trim();

      if (serialBuffer.length() == 0) {
        // ligne vide (ex: "\n" de resynchronisation envoyé par le Pi) : on ignore

      } else if (serialBuffer == "ID?") {
        Serial.println("AQBTCM_LIGHTS");

      } else if (serialBuffer.startsWith("M:")) {
        traiterCommandeM();

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

      } else if (serialBuffer == "OE_OFF") {
        digitalWrite(OE_PIN, HIGH);  // coupure matérielle instantanée de toutes les sorties PWM
      } else if (serialBuffer == "OE_ON") {
        digitalWrite(OE_PIN, LOW);   // réactive les sorties (reprend l'état logiciel courant)

      } else {
        Serial.print("ERR_UNKNOWN_CMD:");
        Serial.println(serialBuffer);
      }
      serialBuffer = "";
    } else if (serialBuffer.length() < 600) {
      serialBuffer += c;
    }
  }

  if (currentOpMode == MORSE) avancerMorse();
}
