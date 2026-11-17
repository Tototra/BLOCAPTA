# Rapport d'audit — ScanTrace v2

**Établissement :** Bloc opératoire central de référence (10 salles, données OPROOM 2026)
**Éditeur :** Société fictive · **Type d'outil :** Traçabilité des dispositifs médicaux par scan du code UDI · **Statut :** En essai
**Généré le :** 2026-11-17 15:42 · rédaction : deterministe

## Verdict

**Score de compatibilité : 100.0/100 — compatible**
**Niveau de confiance de l'analyse : MOYENNE** · Fiche : ANALYSABLE_AVEC_RESERVES · Réglementaire : GO

ScanTrace v2 obtient un score de compatibilité de 100.0/100 (compatible) pour Bloc opératoire central de référence (10 salles, données OPROOM 2026), avec un niveau de confiance moyenne. La simulation couvre 28 jours d'activité et 10 réplications. Le temps total de documentation passe de 42.5 h à 37.7 h (-11.3 %). Facteur humain (scénario « Déploiement selon la fiche (lundi 8 h) ») : en fin de période, la confiance des utilisateurs « ibode » est de 0.66 sur 1.

## Indicateurs clés (moyennes sur 10 réplications de 28 jours)

| Indicateur | Unité | Sans l'outil | Avec l'outil | Écart |
|---|---|---:|---:|---:|
| Temps total consacré à la documentation | h | 42.51 | 37.69 | -11.3 % |
| Temps moyen par tâche de documentation | min | 2.43 | 2.18 | -10.5 % |
| Nombre total de saisies | saisies | 1049.20 | 1039.10 | -1.0 % |
| Éléments potentiellement non documentés | éléments | 0.00 | 0.00 | 0.00 |
| Durée moyenne de parcours | min | 257.37 | 255.16 | -0.9 % |
| Attente moyenne de ressources par étape | min | 6.92 | 6.72 | -2.9 % |
| Taux d'occupation des salles (temps patient / temps d'ouverture) | % | 52.06 | 52.04 | 0.0 % |
| Cas programmés sortant de salle après la fermeture | % | 1.76 | 1.65 | -6.2 % |
| Cas déprogrammés le jour même (règle de fin) | cas | 0.70 | 0.10 | -85.7 % |
| Attente moyenne d'un poste informatique | min | 0.00 | 0.00 | 0.00 |
| Pic d'utilisateurs simultanés du logiciel | utilisateurs | 0.00 | 1.80 | +1.80 |
| Temps de documentation – chirurgien | h | 25.65 | 25.80 | +0.6 % |
| Temps de documentation – ibode | h | 16.86 | 11.89 | -29.5 % |

## Effets humains (scénario « Déploiement selon la fiche (lundi 8 h) »)

Confiance moyenne dans l'outil (0 = aucune, 1 = totale), relevée chaque semaine :

| Métier | S1 | S2 | S3 | S4 | S5 | Utilisation réelle de l'outil |
|---|---:|---:|---:|---:|---:|---:|
| chirurgien | 0.50 | 0.50 | 0.50 | 0.51 | 0.51 | non utilisateur |
| iade | 0.50 | 0.50 | 0.50 | 0.51 | 0.51 | non utilisateur |
| ibode | 0.50 | 0.61 | 0.63 | 0.64 | 0.68 | 100 % |
| mar | 0.50 | 0.50 | 0.50 | 0.51 | 0.51 | non utilisateur |

- Pannes simulées : 4.5 en moyenne (228 min au total)
- Temps moyen d'une saisie avec l'outil, semaine par semaine (courbe d'apprentissage) : 1.75 min → 1.62 min → 1.62 min → 1.48 min
*Mécanismes : aversion à la perte (une panne fait baisser la confiance environ deux fois plus qu'un usage réussi ne la fait monter), influence des collègues pondérée par l'autorité, courbe d'apprentissage. Les coefficients marqués « à calibrer » ne sont pas encore mesurés : lire ces résultats comme des tendances.*

## Frictions détectées par la simulation

| Gravité | Type | Parcours / étape | Rôle | Part des tâches | Occurrences / jour | Heures perdues / jour | Éléments à risque (sur la période) |
|---|---|---|---|---:|---:|---:|---:|
| info | panne | 3 parcours / intervention | ibode | 0.2 % | 0.0 | 0.00 | 0.0 |

## Contrôle de complétude de la fiche (agent 1)

Verdict **ANALYSABLE_AVEC_RESERVES** — confiance **moyenne** — obligatoires 25/25, recommandés 11/12, facultatifs 0/3.

| Champ | Statut requis | État | Raison |
|---|---|---|---|
| B9.etudes — Études ou chiffres publiés | R | Inconnu | L'auteur a écrit « Inconnu ». |

Alertes :
- **affirmation_non_etayee** (B4.etapes) : L'étape « Tracer un implant » annonce un gain de 75 % sans mesure sur site ni étude publiée.
- **affirmation_non_etayee** (B4.etapes) : L'étape « Consulter les alertes de rappel » annonce un gain de 70 % sans mesure sur site ni étude publiée.

## Conformité réglementaire et interopérabilité

Verdict **GO** — conformité pondérée 100.0 %.

Toutes les exigences applicables sont démontrées par la fiche.

## Questions à poser à l'auteur de la fiche ou à l'éditeur
1. Existe-t-il des études publiées (référence complète) ?

## Hypothèses faites pour l'analyse
- Outil simulé uniquement pour : Chirurgie Générale et Digestive, Chirurgie Orthopédique, VISCERAL ROBOT.
- « Tracer un implant » : 0.5 min annoncées par l'éditeur, simulées entre 0.375 et 0.75 min.
- Étape « Consulter les alertes de rappel » non reliée à une tâche du jumeau : non simulée.

## Détail du score

| Motif | Points |
|---|---:|

## Paramètres à calibrer

Ces valeurs ne sont pas encore mesurées sur le terrain ; elles conditionnent la précision des résultats.
- Effectifs par plage horaire : Médecins anesthésistes-réanimateurs (une induction à la fois)
- Effectifs par plage horaire : Infirmiers anesthésistes (IADE)
- Effectifs par plage horaire : Infirmiers de bloc opératoire (IBODE)
- Effectifs par plage horaire : IDE panseurs (circulants)
- Effectifs par plage horaire : IDE de SSPI
- Effectifs par plage horaire : Brancardiers d'installation (salle, table, transfert SSPI)
- Effectifs par plage horaire : Agents de bionettoyage (ASH)
- Patients surveillés par IDE de SSPI : 4
- Effectif : Cardiologues interventionnels
- Postes de pré-anesthésie : 8
- Début des vacations programmées (ouverture et vérification de salle) : 08:30
- Taux de remplissage du programme opératoire : 0.73
- Délai d'appel du patient avant l'heure prévue : 60 min
- Découpage de l'occupation de salle en phases (installation, induction, intervention, réveil)
- Durées de brancardage, d'accueil en pré-anesthésie, de bionettoyage et de transfert
- Durées de SSPI par type d'anesthésie
- Probabilités d'usage des équipements partagés par spécialité
- Nombre d'actes CCAM et de dispositifs médicaux tracés par intervention
- Part de patients venant à pied (debout) par spécialité
- alpha (apprentissage) — à calibrer
- kappa (influence des collègues) — à calibrer
- confiance initiale — à calibrer
- seuil de contournement — à calibrer
- facteur du 1er usage — à calibrer

## Annexe — tous les indicateurs

| Indicateur | Unité | Sans l'outil (IC 95 %) | Avec l'outil (IC 95 %) |
|---|---|---|---|
| Attente moyenne d'un poste informatique | min | 0.00 [0.00 ; 0.00] | 0.00 [0.00 ; 0.00] |
| Attente moyenne de ressources par étape | min | 6.92 [5.64 ; 8.19] | 6.72 [5.42 ; 8.01] |
| Cas annulés avant le bloc | cas | 144.60 [132.19 ; 157.01] | 144.60 [132.19 ; 157.01] |
| Cas déprogrammés le jour même (règle de fin) | cas | 0.70 [-0.65 ; 2.05] | 0.10 [-0.13 ; 0.33] |
| Cas programmés | cas | 866.00 [829.45 ; 902.55] | 866.00 [829.45 ; 902.55] |
| Confiance moyenne dans l'outil – cardiologue | 0-1 | 0.00 [0.00 ; 0.00] | 0.51 [0.50 ; 0.51] |
| Confiance moyenne dans l'outil – chir_gynecologie | 0-1 | 0.00 [0.00 ; 0.00] | 0.51 [0.51 ; 0.52] |
| Confiance moyenne dans l'outil – chir_ophtalmologie | 0-1 | 0.00 [0.00 ; 0.00] | 0.51 [0.51 ; 0.51] |
| Confiance moyenne dans l'outil – chir_orl | 0-1 | 0.00 [0.00 ; 0.00] | 0.51 [0.51 ; 0.51] |
| Confiance moyenne dans l'outil – chir_orthopedie | 0-1 | 0.00 [0.00 ; 0.00] | 0.51 [0.51 ; 0.51] |
| Confiance moyenne dans l'outil – chir_urologie | 0-1 | 0.00 [0.00 ; 0.00] | 0.51 [0.50 ; 0.51] |
| Confiance moyenne dans l'outil – chir_visceral | 0-1 | 0.00 [0.00 ; 0.00] | 0.51 [0.51 ; 0.51] |
| Confiance moyenne dans l'outil – endoscopiste | 0-1 | 0.00 [0.00 ; 0.00] | 0.51 [0.51 ; 0.52] |
| Confiance moyenne dans l'outil – iade | 0-1 | 0.00 [0.00 ; 0.00] | 0.51 [0.51 ; 0.51] |
| Confiance moyenne dans l'outil – ibode | 0-1 | 0.00 [0.00 ; 0.00] | 0.66 [0.62 ; 0.70] |
| Confiance moyenne dans l'outil – mar | 0-1 | 0.00 [0.00 ; 0.00] | 0.51 [0.51 ; 0.51] |
| Contrôle d'ubiquité (doit rester à 0) | violations | 0.00 [0.00 ; 0.00] | 0.00 [0.00 ; 0.00] |
| Dépassement horaire moyen par jour et par service | min | 247.24 [231.25 ; 263.23] | 248.63 [236.61 ; 260.64] |
| Durée médiane d'occupation de salle – prog_cardiologie | min | 9.65 [-5.02 ; 24.33] | 9.65 [-5.02 ; 24.33] |
| Durée médiane d'occupation de salle – prog_chirurgie_generale_et_digestive | min | 104.78 [99.57 ; 109.99] | 104.78 [99.57 ; 109.99] |
| Durée médiane d'occupation de salle – prog_chirurgie_orl | min | 84.45 [78.49 ; 90.42] | 84.45 [78.49 ; 90.42] |
| Durée médiane d'occupation de salle – prog_chirurgie_orthopedique | min | 110.99 [106.82 ; 115.16] | 110.99 [106.82 ; 115.16] |
| Durée médiane d'occupation de salle – prog_chirurgie_urologique | min | 81.59 [76.69 ; 86.49] | 81.59 [76.69 ; 86.49] |
| Durée médiane d'occupation de salle – prog_endoscopie_digestive | min | 34.71 [33.57 ; 35.84] | 34.71 [33.57 ; 35.84] |
| Durée médiane d'occupation de salle – prog_gynecologie_obstetrique | min | 60.88 [56.57 ; 65.20] | 60.88 [56.57 ; 65.20] |
| Durée médiane d'occupation de salle – prog_ophtalmologie | min | 17.33 [16.65 ; 18.00] | 17.33 [16.65 ; 18.00] |
| Durée médiane d'occupation de salle – prog_stomatologie | min | 69.49 [42.42 ; 96.56] | 69.49 [42.42 ; 96.56] |
| Durée médiane d'occupation de salle – prog_urologie_robot | min | 371.01 [307.95 ; 434.07] | 371.01 [307.95 ; 434.07] |
| Durée médiane d'occupation de salle – prog_visceral_robot | min | 208.63 [136.30 ; 280.97] | 208.63 [136.30 ; 280.97] |
| Durée médiane d'occupation de salle – urg_cardiologie | min | 21.22 [1.55 ; 40.90] | 20.87 [1.52 ; 40.22] |
| Durée médiane d'occupation de salle – urg_chirurgie_generale_et_digestive | min | 113.85 [106.66 ; 121.04] | 114.04 [108.36 ; 119.73] |
| Durée médiane d'occupation de salle – urg_chirurgie_orl | min | 98.04 [81.09 ; 114.98] | 76.32 [64.94 ; 87.71] |
| Durée médiane d'occupation de salle – urg_chirurgie_orthopedique | min | 114.78 [111.33 ; 118.24] | 111.94 [106.26 ; 117.63] |
| Durée médiane d'occupation de salle – urg_chirurgie_urologique | min | 86.72 [80.49 ; 92.95] | 82.77 [73.55 ; 91.98] |
| Durée médiane d'occupation de salle – urg_endoscopie_digestive | min | 36.01 [14.11 ; 57.90] | 45.50 [20.61 ; 70.39] |
| Durée médiane d'occupation de salle – urg_gynecologie_obstetrique | min | 62.77 [55.49 ; 70.05] | 63.94 [59.07 ; 68.81] |
| Durée médiane d'occupation de salle – urg_stomatologie | min | 24.40 [-3.72 ; 52.51] | 26.43 [-4.42 ; 57.29] |
| Durée médiane d'occupation de salle – urg_visceral_robot | min | 190.23 [115.16 ; 265.29] | 201.67 [134.40 ; 268.94] |
| Durée moyenne de parcours | min | 257.37 [247.38 ; 267.35] | 255.16 [244.99 ; 265.33] |
| Durée moyenne de parcours – prog_cardiologie | min | 34.98 [-18.25 ; 88.21] | 35.74 [-19.16 ; 90.64] |
| Durée moyenne de parcours – prog_chirurgie_generale_et_digestive | min | 273.28 [268.31 ; 278.26] | 273.30 [268.38 ; 278.21] |
| Durée moyenne de parcours – prog_chirurgie_orl | min | 250.11 [243.01 ; 257.22] | 247.67 [240.68 ; 254.66] |
| Durée moyenne de parcours – prog_chirurgie_orthopedique | min | 256.87 [250.01 ; 263.74] | 257.37 [250.95 ; 263.79] |
| Durée moyenne de parcours – prog_chirurgie_urologique | min | 242.94 [236.64 ; 249.25] | 242.18 [233.79 ; 250.57] |
| Durée moyenne de parcours – prog_endoscopie_digestive | min | 184.50 [177.94 ; 191.05] | 182.76 [177.02 ; 188.50] |
| Durée moyenne de parcours – prog_gynecologie_obstetrique | min | 208.81 [198.97 ; 218.65] | 206.26 [198.83 ; 213.69] |
| Durée moyenne de parcours – prog_ophtalmologie | min | 141.63 [128.35 ; 154.92] | 137.06 [130.51 ; 143.60] |
| Durée moyenne de parcours – prog_stomatologie | min | 183.69 [114.06 ; 253.31] | 184.23 [114.29 ; 254.16] |
| Durée moyenne de parcours – prog_urologie_robot | min | 556.23 [480.43 ; 632.03] | 555.95 [482.68 ; 629.22] |
| Durée moyenne de parcours – prog_visceral_robot | min | 390.35 [274.46 ; 506.24] | 399.45 [275.03 ; 523.87] |
| Durée moyenne de parcours – urg_cardiologie | min | 111.06 [-51.50 ; 273.62] | 125.27 [-58.37 ; 308.90] |
| Durée moyenne de parcours – urg_chirurgie_generale_et_digestive | min | 431.61 [389.40 ; 473.82] | 438.61 [391.40 ; 485.82] |
| Durée moyenne de parcours – urg_chirurgie_orl | min | 388.88 [299.85 ; 477.92] | 357.77 [257.37 ; 458.16] |
| Durée moyenne de parcours – urg_chirurgie_orthopedique | min | 397.89 [356.71 ; 439.07] | 387.74 [347.47 ; 428.01] |
| Durée moyenne de parcours – urg_chirurgie_urologique | min | 375.92 [333.50 ; 418.33] | 371.72 [316.11 ; 427.33] |
| Durée moyenne de parcours – urg_endoscopie_digestive | min | 472.20 [176.35 ; 768.04] | 469.66 [171.53 ; 767.80] |
| Durée moyenne de parcours – urg_gynecologie_obstetrique | min | 374.34 [304.93 ; 443.76] | 363.94 [289.18 ; 438.70] |
| Durée moyenne de parcours – urg_stomatologie | min | 73.46 [-23.36 ; 170.28] | 73.93 [-25.14 ; 172.99] |
| Durée moyenne de parcours – urg_visceral_robot | min | 566.41 [325.47 ; 807.34] | 639.28 [385.67 ; 892.89] |
| Durées négatives tirées (doit rester à 0) | cas | 0.00 [0.00 ; 0.00] | 0.00 [0.00 ; 0.00] |
| Éléments potentiellement non documentés | éléments | 0.00 [0.00 ; 0.00] | 0.00 [0.00 ; 0.00] |
| Heure médiane d'entrée du premier cas (minutes depuis minuit) | min | 510.00 [510.00 ; 510.00] | 510.00 [510.00 ; 510.00] |
| Interventions réalisées par dimanche | cas/j | 4.65 [3.81 ; 5.49] | 4.65 [3.81 ; 5.49] |
| Interventions réalisées par jeudi | cas/j | 42.62 [38.55 ; 46.70] | 42.62 [38.55 ; 46.70] |
| Interventions réalisées par lundi | cas/j | 31.48 [28.08 ; 34.87] | 31.52 [28.17 ; 34.88] |
| Interventions réalisées par mardi | cas/j | 31.60 [29.18 ; 34.02] | 31.60 [29.18 ; 34.02] |
| Interventions réalisées par mercredi | cas/j | 34.25 [31.22 ; 37.28] | 34.25 [31.22 ; 37.28] |
| Interventions réalisées par samedi | cas/j | 5.60 [4.52 ; 6.68] | 5.60 [4.52 ; 6.68] |
| Interventions réalisées par vendredi | cas/j | 29.98 [26.49 ; 33.46] | 30.07 [26.52 ; 33.63] |
| Jours d'activité simulés | jours | 28.00 [28.00 ; 28.00] | 28.00 [28.00 ; 28.00] |
| minutes_de_panne |  | 0.00 [0.00 ; 0.00] | 228.05 [122.66 ; 333.44] |
| Occupation rapportée à la capacité totale (toutes salles × vacation) | % | 49.92 [47.96 ; 51.87] | 49.82 [47.92 ; 51.73] |
| Taux d'occupation des salles (temps patient / temps d'ouverture) | % | 52.06 [50.55 ; 53.57] | 52.04 [50.42 ; 53.67] |
| pannes |  | 0.00 [0.00 ; 0.00] | 4.50 [3.27 ; 5.73] |
| Patients par jour actif – prog_cardiologie | patients/j | 0.04 [-0.02 ; 0.10] | 0.04 [-0.02 ; 0.10] |
| Patients par jour actif – prog_chirurgie_generale_et_digestive | patients/j | 2.34 [2.04 ; 2.64] | 2.34 [2.04 ; 2.64] |
| Patients par jour actif – prog_chirurgie_orl | patients/j | 1.09 [0.84 ; 1.34] | 1.09 [0.84 ; 1.34] |
| Patients par jour actif – prog_chirurgie_orthopedique | patients/j | 3.17 [2.83 ; 3.51] | 3.17 [2.83 ; 3.51] |
| Patients par jour actif – prog_chirurgie_urologique | patients/j | 2.29 [1.88 ; 2.71] | 2.29 [1.88 ; 2.71] |
| Patients par jour actif – prog_endoscopie_digestive | patients/j | 4.30 [3.45 ; 5.15] | 4.31 [3.46 ; 5.17] |
| Patients par jour actif – prog_gynecologie_obstetrique | patients/j | 2.29 [1.96 ; 2.62] | 2.29 [1.96 ; 2.63] |
| Patients par jour actif – prog_ophtalmologie | patients/j | 4.04 [3.37 ; 4.70] | 4.05 [3.39 ; 4.71] |
| Patients par jour actif – prog_stomatologie | patients/j | 0.33 [0.17 ; 0.48] | 0.33 [0.17 ; 0.48] |
| Patients par jour actif – prog_urologie_robot | patients/j | 0.19 [0.10 ; 0.27] | 0.19 [0.10 ; 0.27] |
| Patients par jour actif – prog_visceral_robot | patients/j | 0.21 [0.12 ; 0.30] | 0.21 [0.12 ; 0.30] |
| Patients par jour actif – urg_cardiologie | patients/j | 0.01 [0.00 ; 0.03] | 0.01 [0.00 ; 0.03] |
| Patients par jour actif – urg_chirurgie_generale_et_digestive | patients/j | 1.76 [1.59 ; 1.93] | 1.76 [1.59 ; 1.93] |
| Patients par jour actif – urg_chirurgie_orl | patients/j | 0.19 [0.14 ; 0.23] | 0.19 [0.14 ; 0.23] |
| Patients par jour actif – urg_chirurgie_orthopedique | patients/j | 1.87 [1.63 ; 2.10] | 1.87 [1.63 ; 2.10] |
| Patients par jour actif – urg_chirurgie_urologique | patients/j | 0.71 [0.58 ; 0.85] | 0.71 [0.58 ; 0.85] |
| Patients par jour actif – urg_endoscopie_digestive | patients/j | 0.04 [0.02 ; 0.06] | 0.04 [0.02 ; 0.06] |
| Patients par jour actif – urg_gynecologie_obstetrique | patients/j | 0.79 [0.67 ; 0.90] | 0.79 [0.67 ; 0.90] |
| Patients par jour actif – urg_stomatologie | patients/j | 0.02 [0.00 ; 0.05] | 0.02 [0.00 ; 0.05] |
| Patients par jour actif – urg_visceral_robot | patients/j | 0.07 [0.04 ; 0.10] | 0.07 [0.04 ; 0.10] |
| Patients pris en charge (parcours terminés) | patients | 720.70 [691.60 ; 749.80] | 721.30 [692.13 ; 750.47] |
| Pic d'utilisateurs simultanés du logiciel | utilisateurs | 0.00 [0.00 ; 0.00] | 1.80 [1.35 ; 2.25] |
| Nombre total de saisies | saisies | 1049.20 [1004.07 ; 1094.33] | 1039.10 [999.11 ; 1079.09] |
| Taux d'annulation | % | 16.67 [15.58 ; 17.76] | 16.67 [15.58 ; 17.76] |
| Cas programmés sortant de salle après la fermeture | % | 1.76 [1.36 ; 2.16] | 1.65 [1.28 ; 2.02] |
| Taux d'utilisation effective de l'outil – ibode | % | 0.00 [0.00 ; 0.00] | 100.00 [100.00 ; 100.00] |
| Temps total consacré à la documentation | h | 42.51 [40.66 ; 44.36] | 37.69 [36.22 ; 39.16] |
| Temps de documentation – cardiologue | h | 0.06 [0.00 ; 0.12] | 0.06 [-0.01 ; 0.13] |
| Temps de documentation – chir_gynecologie | h | 3.07 [2.69 ; 3.45] | 3.10 [2.70 ; 3.51] |
| Temps de documentation – chir_ophtalmologie | h | 4.01 [3.37 ; 4.66] | 4.06 [3.40 ; 4.72] |
| Temps de documentation – chir_orl | h | 1.60 [1.26 ; 1.93] | 1.61 [1.29 ; 1.93] |
| Temps de documentation – chir_orthopedie | h | 5.04 [4.51 ; 5.56] | 5.08 [4.56 ; 5.60] |
| Temps de documentation – chir_urologie | h | 3.19 [2.69 ; 3.69] | 3.20 [2.64 ; 3.75] |
| Temps de documentation – chir_visceral | h | 4.33 [3.98 ; 4.68] | 4.33 [3.94 ; 4.72] |
| Temps de documentation – endoscopiste | h | 4.36 [3.54 ; 5.18] | 4.36 [3.50 ; 5.22] |
| Temps de documentation – ibode | h | 16.86 [15.57 ; 18.14] | 11.89 [11.10 ; 12.69] |
| Temps moyen par tâche de documentation | min | 2.43 [2.40 ; 2.46] | 2.18 [2.16 ; 2.19] |
| Taux d'occupation – amplificateur | % | 5.25 [4.74 ; 5.76] | 5.31 [4.69 ; 5.93] |
| Taux d'occupation – ash | % | 6.30 [6.02 ; 6.59] | 6.34 [6.05 ; 6.64] |
| Taux d'occupation – brancardier_bloc | % | 7.36 [7.08 ; 7.64] | 7.36 [7.10 ; 7.63] |
| Taux d'occupation – brancardier_service | % | 21.83 [21.04 ; 22.61] | 21.81 [21.04 ; 22.57] |
| Taux d'occupation – cardiologue | % | 0.09 [-0.01 ; 0.19] | 0.09 [-0.01 ; 0.19] |
| Taux d'occupation – chir_gynecologie | % | 4.10 [3.52 ; 4.68] | 4.15 [3.54 ; 4.75] |
| Taux d'occupation – chir_ophtalmologie | % | 1.95 [1.63 ; 2.27] | 1.96 [1.64 ; 2.28] |
| Taux d'occupation – chir_orl | % | 4.19 [3.36 ; 5.03] | 4.09 [3.27 ; 4.90] |
| Taux d'occupation – chir_orthopedie | % | 10.59 [9.46 ; 11.72] | 10.35 [9.23 ; 11.47] |
| Taux d'occupation – chir_urologie | % | 6.73 [5.45 ; 8.00] | 6.74 [5.43 ; 8.04] |
| Taux d'occupation – chir_visceral | % | 10.97 [9.98 ; 11.96] | 10.91 [9.98 ; 11.84] |
| Taux d'occupation – colonne_coelioscopie | % | 5.79 [5.32 ; 6.27] | 6.31 [5.69 ; 6.93] |
| Taux d'occupation – echographe | % | 2.97 [2.70 ; 3.25] | 3.31 [2.88 ; 3.74] |
| Taux d'occupation – endoscopiste | % | 2.28 [1.86 ; 2.70] | 2.28 [1.86 ; 2.70] |
| Taux d'occupation – iade | % | 53.01 [51.39 ; 54.64] | 52.76 [51.15 ; 54.36] |
| Taux d'occupation – ibode | % | 33.89 [32.91 ; 34.88] | 33.64 [32.61 ; 34.67] |
| Taux d'occupation – ide_bloc | % | 24.55 [22.94 ; 26.17] | 23.65 [22.47 ; 24.84] |
| Taux d'occupation – ide_sspi | % | 0.00 [0.00 ; 0.00] | 0.00 [0.00 ; 0.00] |
| Taux d'occupation – ide_sspi_place | % | 11.41 [10.78 ; 12.05] | 11.38 [10.76 ; 12.00] |
| Taux d'occupation – lit_sspi | % | 6.25 [5.90 ; 6.59] | 6.23 [5.89 ; 6.57] |
| Taux d'occupation – mar | % | 19.11 [18.57 ; 19.65] | 19.11 [18.55 ; 19.66] |
| Taux d'occupation – mar_supervision | % | 21.16 [20.61 ; 21.70] | 21.15 [20.57 ; 21.72] |
| Taux d'occupation – microscope | % | 2.36 [2.02 ; 2.69] | 2.44 [2.17 ; 2.70] |
| Taux d'occupation – poste_preanesthesie | % | 9.33 [8.62 ; 10.04] | 9.20 [8.63 ; 9.78] |
| Taux d'occupation – poste_salle | % | 0.36 [0.34 ; 0.37] | 0.36 [0.34 ; 0.37] |
| Taux d'occupation – robot | % | 5.33 [4.12 ; 6.54] | 5.37 [4.18 ; 6.56] |
| Taux d'occupation – salle_op | % | 62.08 [60.05 ; 64.11] | 61.81 [59.74 ; 63.88] |

---
*Méthode : jumeau numérique du bloc opératoire (simulation à événements discrets et à agents), scénarios « sans outil » et « avec outil » sur les mêmes patients, graine 42. Blocapta aide à décider : il ne remplace ni l'avis des soignants ni un essai réel. Les chiffres du texte sont vérifiés automatiquement contre les résultats de simulation.*
