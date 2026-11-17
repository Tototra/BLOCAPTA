# Questionnaire de paramétrage du jumeau numérique BLOCAPTA (bloc opératoire)

Ce questionnaire permet de reproduire fidèlement votre bloc opératoire afin d'évaluer l'effet d'un logiciel avant son déploiement. Il est à remplir par la DSI avec le cadre de bloc. Donnez des ordres de grandeur si vous n'avez pas de chiffres exacts ; écrivez « inconnu » sinon : la valeur de référence est alors conservée et signalée « à calibrer » dans les rapports. Les exports horodatés (section G) sont la source la plus précieuse : ils permettent de calibrer automatiquement les durées et de passer le test de fidélité (écart inférieur à 10 % avec la réalité).

> Renvoyez vos réponses dans le fichier `reponses.yaml` (généré par `blocapta template --answers`).

## A. Établissement

| Réf. | Question | Format / exemple | Réponse |
|---|---|---|---|
| A1 | Nom de l'établissement **(obligatoire)** | `text` | |
| A2 | Type d'établissement **(obligatoire)**<br><sub>CHU, CH, clinique privée MCO, ESPIC</sub> | `text` | |
| A3 | Nombre total de lits et places | `int` | |
| A4 | Nombre de blocs et de sites (le jumeau simule un bloc à la fois) | `text` | |
| A5 | Numéro FINESS (facultatif) | `text` | |

## B. Salles, vacations et programme opératoire

| Réf. | Question | Format / exemple | Réponse |
|---|---|---|---|
| B1 | Nombre de salles d'opération du bloc **(obligatoire)** | `int (salles)` | |
| B2 | Horaires d'ouverture des salles en semaine **(obligatoire)** | `08:00-18:30` | |
| B3 | Heure de début du premier cas programmé (après ouverture et vérification de la salle) | `08:30` | |
| B4 | Heure au-delà de laquelle on ne démarre plus un cas programmé | `18:00` | |
| B5 | Heure de fin théorique de l'activité (pour mesurer les débordements) | `18:30` | |
| B6 | Délai moyen de remise en état entre deux cas programmés (minutes) | `7` | |
| B7 | Délai d'appel du patient avant l'heure prévue d'entrée en salle (minutes) | `60` | |
| B8 | Nombre de salles réservées aux urgences la nuit et le week-end | `1` | |
| B9 | Organisation des vacations (planning hebdomadaire chirurgien / salle / spécialité)<br><sub>Joindre le planning type ; il permet de remplacer la répartition statistique des salles.</sub> | `text` | |
| B10 | Taux d'occupation, de débordement et d'annulation suivis (et leur mode de calcul)<br><sub>Indispensable pour comparer le jumeau à vos tableaux de bord avec la même définition.</sub> | `text` | |

## C. Pré-anesthésie, SSPI et aval

| Réf. | Question | Format / exemple | Réponse |
|---|---|---|---|
| C1 | Nombre de postes en salle de pré-anesthésie (assis et couchés) | `int` | |
| C2 | L'ALR est-elle réalisée en pré-anesthésie (temps masqué) ? | `text` | |
| C3 | Nombre de lits de SSPI **(obligatoire)** | `int` | |
| C4 | Qui décide la sortie de SSPI et comment (score, MAR présent) ? | `text` | |
| C5 | Lits d'aval disponibles et heure de fermeture de l'ambulatoire | `text` | |

## D. Équipes et horaires

| Réf. | Question | Format / exemple | Réponse |
|---|---|---|---|
| D1 | Effectifs et horaires des MAR (combien sont présents simultanément, par plage) **(obligatoire)** | `8h-17h : 4 ; 8h-20h : 3 ; 20h-8h : 1` | |
| D2 | Effectifs et horaires des IADE **(obligatoire)** | `1 par salle ouverte + 1 ; nuit : 1` | |
| D3 | Effectifs et horaires des IBODE et IDE panseurs **(obligatoire)** | `text` | |
| D4 | Effectifs et horaires des brancardiers (service ↔ bloc, et installation) | `text` | |
| D5 | Effectifs et horaires des IDE de SSPI et des agents de bionettoyage | `text` | |
| D6 | Chirurgiens par spécialité et organisation de la garde (sur place ou astreinte, délai de venue) | `text` | |
| D7 | Taux d'absentéisme et recours à l'intérim | `text` | |

## E. Équipements partagés

| Réf. | Question | Format / exemple | Réponse |
|---|---|---|---|
| E1 | Nombre d'amplificateurs de brillance | `int` | |
| E2 | Nombre de colonnes de coelioscopie / endoscopie | `int` | |
| E3 | Nombre de robots chirurgicaux | `int` | |
| E4 | Nombre de microscopes opératoires | `int` | |
| E5 | Nombre d'échographes d'anesthésie | `int` | |
| E6 | Nombre de postes informatiques en salle (et sont-ils mobiles ?) | `int` | |

## F. Traçabilité et système d'information

| Réf. | Question | Format / exemple | Réponse |
|---|---|---|---|
| F1 | Répartition du nombre d'actes CCAM codés par intervention<br><sub>Part des interventions avec 1, 2, 3, 4 actes. Information clé pour les outils de traçabilité (à demander au DIM).</sub> | `{1: 0.55, 2: 0.30, 3: 0.12, 4: 0.03}` | |
| F2 | Temps de saisie des actes aujourd'hui, par saisie (min / mode / max, en minutes) | `[0.5, 1, 2]` | |
| F3 | Temps de traçabilité d'un dispositif médical implanté aujourd'hui (min / mode / max, en minutes) | `[1, 2, 3]` | |
| F4 | Éditeur et produit du logiciel de bloc | `text` | |
| F5 | Éditeur et produit du DPI | `text` | |
| F6 | Interfaces existantes (source → cible, standard, message)<br><sub>Ex. logiciel de bloc → DPI en HL7 v2</sub> | `text` | |
| F7 | L'établissement utilise-t-il une authentification unique (SSO) ? | `bool` | |
| F8 | Politique d'hébergement (on_premise, cloud_hds, mixte) | `text` | |
| F9 | Plateforme d'intégration (EAI), couverture Wi-Fi au bloc | `text` | |

## G. Données horodatées pour la calibration (pseudonymisées)

| Réf. | Question | Format / exemple | Réponse |
|---|---|---|---|
| G1 | Export des interventions (date, heure, salle, spécialité, type, durée, annulation et motif) **(obligatoire)**<br><sub>Format OPROOM : c'est la base du bloc de référence.</sub> | `text` | |
| G2 | Horodatages complets du parcours (arrivée en pré-anesthésie, entrée en salle, incision, fin, sortie, arrivée et sortie de SSPI) | `text` | |
| G3 | Mode d'arrivée du patient (debout, fauteuil, couché) et nombre de brancards | `text` | |
| G4 | Annulations du jour même avec leur moment (veille, arrivée, pré-anesthésie) | `text` | |
| G5 | Classes d'urgence et délais réels de prise en charge | `text` | |
| G6 | Affectation réelle des MAR en salle (et non seulement le référent du dossier) | `text` | |
| G7 | Période couverte (idéalement 3 mois ou plus) et format des fichiers | `text` | |
| G8 | Modalités de pseudonymisation (noms des soignants remplacés par des codes) et validation DPO / RSSI **(obligatoire)** | `text` | |

## H. Organisation, irritants et sécurité

| Réf. | Question | Format / exemple | Réponse |
|---|---|---|---|
| H1 | Doubles saisies, contournements ou outils abandonnés connus<br><sub>Précieux pour vérifier que le jumeau reproduit les problèmes réels.</sub> | `text` | |
| H2 | Pics d'activité connus (jour de semaine, saison, relève) | `text` | |
| H3 | Exigences PSSI / homologation applicables aux nouveaux logiciels | `text` | |
| H4 | Référents (DSI, RSSI, DPO, cadre de bloc, DIM, équipe d'anesthésie) | `text` | |
