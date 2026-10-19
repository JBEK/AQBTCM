# AQBTCM — fiche commandes série (ESP32_MOTORS + ESP32_LIGHTS)

Moniteur Série Arduino : **115200 baud**, terminaison de ligne **"Newline"**.
Chaque carte répond `ID?` par son nom pour s'identifier.

---

## ⚠️ Alimentation — panne du Raspberry Pi 4 (oct. 2026) et corrections

**Ce qui s'est passé** : plantages USB répétés, puis le Pi 4 s'est éteint d'un
coup et ne redémarre plus (LED rouge fixe). Hypothèse retenue : chaque ESP32
était alimenté à la fois par USB (depuis le Pi) **et** en externe via VIN, sur
une carte où USB-5V et VIN sont reliés en interne sans isolation — avec en
plus deux alimentations à découpage différentes pour les deux ESP32. Ça a pu
faire remonter du courant par l'USB vers le circuit d'alimentation du Pi
(back-powering), aggravé par un possible écart de masse entre les deux alims
(boucle de masse).

**Correction à appliquer au remontage** :
1. Chaque **ESP32** est alimenté **uniquement par USB** (PC/Pi) — plus
   d'alimentation externe sur sa broche VIN.
2. Les **modules** qui ont besoin de plus de courant/tension (PCA9685 +
   MOSFETs côté lumières, drivers TMC2209 + moteurs côté perceuses) gardent
   leur alimentation 24V externe, comme prévu depuis le début.
3. Toutes les **masses reliées en un seul point** (étoile) : PC/ESP32, chaque
   alim 24V — pas de chaîne de masse d'une carte à l'autre.
4. Si possible, **une seule alimentation 24V** pour les deux cartes plutôt que
   deux différentes ; sinon, au moins les brancher sur la même multiprise.

**Protections ajoutées en plus** :
- 2× isolateur USB **ADuM3160** (1500V, 12 Mbps), un entre le PC et chaque
  ESP32 — modèle choisi : dongle scellé USB-A mâle/femelle, aucun réglage/jumper.
- 1 ferrite (tore) clipsé sur chaque câble USB.

**Avant de tout rebrancher** : câble USB débranché, mesurer au multimètre
l'écart de tension entre la masse de chaque alimentation 24V et la masse du
PC/Pi. Un écart de plusieurs volts indique un vrai problème de câblage
électrique à régler avant de reconnecter quoi que ce soit.

---

## ESP32_MOTORS (perceuses)

### Identification

| Commande | Effet | Réponse |
|---|---|---|
| `ID?` | identification de la carte | `AQBTCM_MOTORS` |

### Contrôle des moteurs

| Commande | Effet |
|---|---|
| `D1:START` / `D2:START` / `D3:START` | démarre la perceuse 1/2/3 (même numéro que le bouton du GUI ; repart toujours horaire, rampe accel douce) |
| `D1:STOP` / `D2:STOP` / `D3:STOP` | arrête cette perceuse (roue libre, driver désactivé) |
| `D:ALL:START` | démarre les 3 moteurs |
| `D:ALL:STOP` | arrête les 3 moteurs |

Un moteur en marche alterne automatiquement horaire/antihoraire toutes les 18s,
avec une rampe accélération/décélération de 500ms à chaque changement de sens.

### Battement de cœur (pause/reprise)

| Commande | Effet |
|---|---|
| `H:START` | met en pause tous les moteurs actuellement actifs (garde leur position dans le cycle, roue libre) |
| `H:STOP` | relance uniquement les moteurs qui étaient actifs avant la pause |

### Erreurs possibles

| Réponse | Signification |
|---|---|
| `ERR_DRILL_ID:<n>` | identifiant de perceuse invalide (doit être 1, 2 ou 3) |
| `ERR_FORMAT_D` | commande `D...` mal formée (ni START ni STOP) |
| `ERR_UNKNOWN_CMD:<cmd>` | commande non reconnue |

### Câblage réel

| | DIR | STEP | EN | Adresse TMC (MS1/MS2 mesurée) |
|---|---|---|---|---|
| Perceuse 1 | D19 | D18 | D5 | 0 |
| Perceuse 2 | D27 | D26 | D25 | 2 |
| Perceuse 3 | D33 | D32 | D14 | 1 |

Les adresses des perceuses 2 et 3 sont inversées par rapport à ce qu'on
attendait à l'origine (confirmé au multimètre) — le firmware en tient compte
(`TMC_ADDR[] = {0, 2, 1}`), pas besoin de re-souder les jumpers MS1/MS2.

UART2 partagé (TMC2209 ×3) : RX = D21, TX = D22.

---

## ESP32_LIGHTS (bandeaux LED + fumée)

### Identification

| Commande | Effet | Réponse |
|---|---|---|
| `ID?` | identification de la carte | `AQBTCM_LIGHTS` |

### Manuel

| Commande | Effet | Réponse |
|---|---|---|
| `P<canal>:<valeur>` | PWM manuel sur 1 canal PCA9685 (canal 0-15, valeur 0-255) — ex `P0:255` | `OK` ou `ERR_CH_UNMANAGED:<n>` / `ERR_FORMAT_P` |

### Morse

| Commande | Effet | Réponse |
|---|---|---|
| `M:<soliste>\|<phrase avec *mots* marqués>` | séquence morse — ex `M:B\|Les *Muses* dansent` : le groupe B (soliste) épelle toute la phrase. Quand il arrive sur un mot entre `*...*`, les 2 autres groupes (chœurs) se mettent à réciter ce mot **en boucle**, doucement, et **continuent pendant les phrases suivantes** jusqu'au prochain mot marqué (ils basculent alors dessus). Les `M:` enchaînés ne coupent pas les chœurs. Caractères reconnus : A-Z et 0-9 uniquement (le Pi retire les accents avant l'envoi). Ligne max 600 caractères. | `OK` quand le **soliste** a fini sa phrase (les chœurs continuent), ou `ERR_FORMAT_M` |
| `M:<soliste>\|<phrase>\|*<motChoeur>*` | ancien format, toujours accepté — ex `M:A\|BONJOUR\|*JOUR*` : le chœur récite son mot dès le début de la phrase | idem |

Réglages morse (durées, luminosités, fondus du soliste et des chœurs) : constantes en haut de `esp32_lights.ino`.
Le firmware est entièrement non-bloquant (aucun `delay()` dans `loop()`) : le soliste n'est jamais figé par un fondu de chœur.

### Battement de cœur

| Commande | Effet |
|---|---|
| `H:<valeur 0-255>` | mode heartbeat : même intensité sur les 3 groupes WW (12 canaux, le CW n'est jamais touché) — ex `H:200` |
| `H:STOP` | sort du mode heartbeat, éteint tout |

### Fumée

| Commande | Effet |
|---|---|
| `FUM_ON` | relais fumée ON |
| `FUM_OFF` | relais fumée OFF |

### Coupure matérielle (Output Enable)

| Commande | Effet |
|---|---|
| `OE_OFF` | coupe instantanément toutes les sorties PWM (indépendant de l'état logiciel morse/heartbeat, qui continue en interne) |
| `OE_ON` | réactive les sorties, reprend l'état logiciel courant |

### Erreurs possibles

| Réponse | Signification |
|---|---|
| `ERR_CH_UNMANAGED:<n>` | canal PCA9685 hors mapping (pas 0-14) |
| `ERR_FORMAT_P` / `ERR_FORMAT_M` | commande mal formée |
| `ERR_UNKNOWN_CMD:<cmd>` | commande non reconnue |

### Mapping PCA9685 (15 canaux sur 16)

| Groupe | Canaux tubes WW (individuels) | Canal CW (bundle des 4 tubes) |
|---|---|---|
| A (luminaire 1) | 0, 1, 2, 3 | 12 |
| B (luminaire 2) | 4, 5, 6, 7 | 13 |
| C (luminaire 3) | 8, 9, 10, 11 | 14 |

Canal 15 : libre. Le CW n'est accessible qu'en manuel (`P12:...`, `P13:...`, `P14:...`),
jamais piloté automatiquement par le morse ou le heartbeat.

### Câblage réel — modules MOSFET

| Module | IN1-4 | IN5-7/8 |
|---|---|---|
| Module 1 | Luminaire 1, tubes WW 1-4 (canaux 0-3) | Luminaire 2, tubes WW 1-4 (canaux 4-7) |
| Module 2 | Luminaire 3, tubes WW 1-4 (canaux 8-11) | CW luminaire 1/2/3 (canaux 12/13/14), IN8 libre |

OE (Output Enable, actif bas) sur D5. I2C : SDA=D21, SCL=D22. Relais fumée sur D27 (côté opposé, pour le routage). PWM à 1kHz.
