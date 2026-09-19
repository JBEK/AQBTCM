# AQBTCM — fiche commandes série (ESP32_MOTORS + ESP32_LIGHTS)

Moniteur Série Arduino : **115200 baud**, terminaison de ligne **"Newline"**.
Chaque carte répond `ID?` par son nom pour s'identifier.

---

## ESP32_MOTORS (perceuses)

### Identification

| Commande | Effet | Réponse |
|---|---|---|
| `ID?` | identification de la carte | `AQBTCM_MOTORS` |

### Contrôle des moteurs

| Commande | Effet |
|---|---|
| `D0:START` / `D1:START` / `D2:START` | démarre le moteur 0/1/2 (repart toujours horaire, rampe accel douce) |
| `D0:STOP` / `D1:STOP` / `D2:STOP` | arrête ce moteur (roue libre, driver désactivé) |
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
| `ERR_DRILL_ID:<n>` | identifiant de moteur invalide (doit être 0, 1 ou 2) |
| `ERR_FORMAT_D` | commande `D...` mal formée (ni START ni STOP) |
| `ERR_UNKNOWN_CMD:<cmd>` | commande non reconnue |

### Câblage réel

| | DIR | STEP | EN | Adresse TMC (MS1/MS2) |
|---|---|---|---|---|
| Moteur 0 | D19 | D18 | D5 | 0 |
| Moteur 1 | D27 | D26 | D25 | 1 |
| Moteur 2 | D33 | D32 | D14 | 2 |

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

OE (Output Enable, actif bas) sur D5. I2C : SDA=D21, SCL=D22. Relais fumée sur D4. PWM à 1kHz.
