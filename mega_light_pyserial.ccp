#include <Arduino.h>

// Prototypes des fonctions
void declamer(String solisteGroupe, String phraseRecue, String motChoeurRecue);
void avancerMorseSoliste(const int* pins, const String& code, int& indexSignal, bool& ledAllume, unsigned long& timer);
void avancerMorseChoeurs(const int* pins1, const int* pins2, const String& code, int& indexSignal, bool& ledAllume, unsigned long& timer);

// Pins des groupes
const int pinsA[] = {2, 3, 4, 5};
const int pinsB[] = {7, 8, 9, 10};
const int pinsC[] = {12, 13, 44, 45};

// Durées morse en ms
const int dotDuration = 200;
const int dashDuration = 600;
const int intraCharPause = 200;
const int interCharPause = 600;
const int interWordPause = 1400;

// Variables globales
String soliste = "";
String phrase = "";
String choeurMot = "";
String choeurGroupes[2];

bool morseEnCours = false;
bool okEnvoye = false; // Nouveau flag pour envoyer "OK" une fois

// Variables soliste
const int* solistePins = nullptr;
String solisteCode = "";
int indexSignalSoliste = 0;
bool solisteLedAllume = false;
unsigned long solisteTimer = 0;

// Variables choeurs (communs aux 2 groupes)
const int* choeurPins1 = nullptr;
const int* choeurPins2 = nullptr;
String choeurCode = "";
int indexSignalChoeur = 0;
bool choeurLedAllume = false;
unsigned long choeurTimer = 0;

// Buffer lecture série
String serialBuffer = "";

// Allumer ou éteindre un groupe avec une intensité PWM
void setGroupPWM(const int* pins, int brightness) {
  for (int i = 0; i < 4; i++) {
    analogWrite(pins[i], brightness);
  }
}

// Fonction pour appliquer PWM sur une seule broche, si elle est dans les groupes
void setPinPWM(int pin, int brightness) {
  // On vérifie si la broche fait partie des pins A, B ou C
  bool found = false;
  for (int i = 0; i < 4; i++) {
    if (pinsA[i] == pin || pinsB[i] == pin || pinsC[i] == pin) {
      found = true;
      break;
    }
  }
  if (found) {
    analogWrite(pin, brightness);
  } else {
    // Broche non prise en charge, on peut ignorer ou envoyer un message
    Serial.print("Pin non supportee: ");
    Serial.println(pin);
  }
}

// Convertir lettre en morse
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
    case ' ': return " "; // pause mot
    default: return "";
  }
}

// Convertir phrase en morse avec espaces entre lettres
String phraseToMorse(const String& texte) {
  String resultat = "";
  for (unsigned int i = 0; i < texte.length(); i++) {
    char c = texte.charAt(i);
    String morse = lettreToMorse(c);
    if (morse == "") continue;
    if (morse == " ") {
      resultat += " ";  // pause mot
    } else {
      resultat += morse + " ";
    }
  }
  return resultat;
}

// Avancer morse soliste (fade rapide)
void avancerMorseSoliste(const int* pins, const String& code, int& indexSignal, bool& ledAllume, unsigned long& timer) {
  if (code.length() == 0) return;

  unsigned long now = millis();

  if (indexSignal >= code.length()) {
    return;
  }

  char c = code.charAt(indexSignal);

  if (!ledAllume) {
    if (c == '.' || c == '-') {
      for (int bri = 0; bri <= 255; bri += 51) {
        setGroupPWM(pins, bri);
        delay(15);
      }
      timer = now;
      ledAllume = true;
    } else if (c == ' ') {
      if (now - timer >= interCharPause) {
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
        setGroupPWM(pins, bri);
        delay(15);
      }
      ledAllume = false;
      indexSignal++;
      timer = now;
    }
  }
}

// Avancer morse choeurs (fade lent synchronisé)
void avancerMorseChoeurs(const int* pins1, const int* pins2, const String& code, int& indexSignal, bool& ledAllume, unsigned long& timer) {
  if (code.length() == 0) return;

  unsigned long now = millis();

  if (indexSignal >= code.length()) {
    return;
  }

  char c = code.charAt(indexSignal);

  if (!ledAllume) {
    if (c == '.' || c == '-') {
      for (int bri = 20; bri <= 120; bri += 10) {
        setGroupPWM(pins1, bri);
        setGroupPWM(pins2, bri);
        delay(50);
      }
      timer = now;
      ledAllume = true;
    } else if (c == ' ') {
      if (now - timer >= interCharPause * 2) {
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
        setGroupPWM(pins1, bri);
        setGroupPWM(pins2, bri);
        delay(50);
      }
      ledAllume = false;
      indexSignal++;
      timer = now;
    }
  }
}

// Initialise déclamation
void declamer(String solisteGroupe, String phraseRecue, String motChoeurRecue) {
  String groupes[3] = {"A", "B", "C"};
  int idxSoliste = 0;
  for (int i = 0; i < 3; i++) {
    if (groupes[i] == solisteGroupe) idxSoliste = i;
  }
  int idxChoeur1 = (idxSoliste + 1) % 3;
  int idxChoeur2 = (idxSoliste + 2) % 3;

  choeurGroupes[0] = groupes[idxChoeur1];
  choeurGroupes[1] = groupes[idxChoeur2];
  soliste = solisteGroupe;
  phrase = phraseRecue;
  choeurMot = motChoeurRecue;

  Serial.print("Soliste: "); Serial.println(soliste);
  Serial.print("Choeurs: "); Serial.print(choeurGroupes[0]); Serial.print(", "); Serial.println(choeurGroupes[1]);
  Serial.print("Phrase: "); Serial.println(phrase);
  Serial.print("Mot choeurs: "); Serial.println(choeurMot);

  if (soliste == "A") solistePins = pinsA;
  else if (soliste == "B") solistePins = pinsB;
  else solistePins = pinsC;

  if (choeurGroupes[0] == "A") choeurPins1 = pinsA;
  else if (choeurGroupes[0] == "B") choeurPins1 = pinsB;
  else choeurPins1 = pinsC;

  if (choeurGroupes[1] == "A") choeurPins2 = pinsA;
  else if (choeurGroupes[1] == "B") choeurPins2 = pinsB;
  else choeurPins2 = pinsC;

  solisteCode = phraseToMorse(phrase);
  choeurCode = phraseToMorse(choeurMot);

  indexSignalSoliste = 0;
  indexSignalChoeur = 0;
  solisteLedAllume = false;
  choeurLedAllume = false;
  morseEnCours = true;
  okEnvoye = false;

  setGroupPWM(pinsA, 0);
  setGroupPWM(pinsB, 0);
  setGroupPWM(pinsC, 0);
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  for (int i = 0; i < 4; i++) {
    pinMode(pinsA[i], OUTPUT);
    pinMode(pinsB[i], OUTPUT);
    pinMode(pinsC[i], OUTPUT);
  }

  setGroupPWM(pinsA, 0);
  setGroupPWM(pinsB, 0);
  setGroupPWM(pinsC, 0);

  Serial.println("Prêt à recevoir commande morse...");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      serialBuffer.trim();

      if (serialBuffer.startsWith("M:")) {
        int pos1 = serialBuffer.indexOf(':');
        int pos2 = serialBuffer.indexOf('|', pos1 + 1);
        int pos3 = serialBuffer.indexOf('|', pos2 + 1);
        int posStar1 = serialBuffer.indexOf('*', pos3 + 1);
        int posStar2 = serialBuffer.indexOf('*', posStar1 + 1);

        if (pos1 != -1 && pos2 != -1 && pos3 != -1 && posStar1 != -1 && posStar2 != -1) {
          String solisteRecue = serialBuffer.substring(pos1 + 1, pos2);
          String phraseRecue = serialBuffer.substring(pos2 + 1, pos3);
          String motChoeurRecue = serialBuffer.substring(posStar1 + 1, posStar2);
          declamer(solisteRecue, phraseRecue, motChoeurRecue);
        }

      } else if (serialBuffer.startsWith("P")) {
        int sep = serialBuffer.indexOf(':');
        if (sep > 0) {
          int pin = serialBuffer.substring(1, sep).toInt();
          int val = serialBuffer.substring(sep + 1).toInt();
          // Vérifier que la pin fait partie des pins A/B/C et val est valide
          bool found = false;
          for (int i = 0; i < 4; i++) {
            if (pinsA[i] == pin || pinsB[i] == pin || pinsC[i] == pin) {
              found = true;
              break;
            }
          }
          if (found && val >= 0 && val <= 255) {
            analogWrite(pin, val);
            Serial.println("OK");
          } else {
            Serial.println("ERR");
          }
        }
      }

      serialBuffer = "";
    } else {
      serialBuffer += c;
    }
  }

  if (morseEnCours) {
    avancerMorseSoliste(solistePins, solisteCode, indexSignalSoliste, solisteLedAllume, solisteTimer);
    avancerMorseChoeurs(choeurPins1, choeurPins2, choeurCode, indexSignalChoeur, choeurLedAllume, choeurTimer);

    // Fin de lecture morse ?
    if (indexSignalSoliste >= solisteCode.length() && indexSignalChoeur >= choeurCode.length()) {
      morseEnCours = false;
      if (!okEnvoye) {
        Serial.println("OK");
        okEnvoye = true;
      }
      setGroupPWM(pinsA, 0);
      setGroupPWM(pinsB, 0);
      setGroupPWM(pinsC, 0);
    }
  }
}
