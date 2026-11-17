# Rapport d'audit — ArchivActes v2.3

**Établissement :** Bloc opératoire central de référence (10 salles, données OPROOM 2026)
**Éditeur :** MedTrace SAS (société fictive) · **Type d'outil :** Traçabilité des actes opératoires · **Statut :** À l'étude
**Généré le :** 2026-11-17 15:42 · rédaction : deterministe

## Verdict

**Score de compatibilité : 40.0/100 — non déployable en l'état (exigence réglementaire obligatoire manquante)**
**Niveau de confiance de l'analyse : FAIBLE** · Fiche : ANALYSABLE_AVEC_RESERVES · Réglementaire : NO_GO

ArchivActes v2.3 obtient un score de compatibilité de 40.0/100 (non déployable en l'état (exigence réglementaire obligatoire manquante)) pour Bloc opératoire central de référence (10 salles, données OPROOM 2026), avec un niveau de confiance faible. Exigence(s) réglementaire(s) obligatoire(s) non démontrée(s) : Conformité RGPD et analyse d'impact (AIPD) réalisée avant déploiement. La simulation couvre 28 jours d'activité et 10 réplications. Le temps total de documentation passe de 42.5 h à 92.9 h (+118.6 %). Facteur humain (scénario « Déploiement selon la fiche (lundi 8 h) ») : en fin de période, la confiance des utilisateurs « chirurgien » est de 0.47 sur 1. 2 point(s) de vigilance ont été identifiés.

## Points de vigilance
### 1. Interface manquante : double saisie — critique

- **Constat :** Aucun flux vers 'logiciel_bloc' : double saisie. Concerne 99.1 % des tâches 'tracabilite_actes' (25.5 occurrences par jour d'activité).
- **Impact :** 0.91 h perdues par jour d'activité pour le rôle 'chirurgien' (25.5 h sur 28 jours simulés).
- **Recommandation :** Conditionner le déploiement au développement du connecteur manquant (via l'EAI).

### 2. Nombre d'éléments par saisie insuffisant — critique

- **Constat :** 4 éléments à documenter, 4 saisies (max 1 par saisie). Concerne 44.0 % des tâches 'tracabilite_actes' (11.3 occurrences par jour d'activité).
- **Impact :** 0.36 h perdues par jour d'activité pour le rôle 'chirurgien' (10.0 h sur 28 jours simulés), 21.8 éléments à risque d'omission.
- **Recommandation :** Exiger de l'éditeur la saisie de plusieurs éléments par fiche, ou chiffrer le temps perdu avant signature.

## Indicateurs clés (moyennes sur 10 réplications de 28 jours)

| Indicateur | Unité | Sans l'outil | Avec l'outil | Écart |
|---|---|---:|---:|---:|
| Temps total consacré à la documentation | h | 42.51 | 92.92 | +118.6 % |
| Temps moyen par tâche de documentation | min | 2.43 | 5.37 | +120.7 % |
| Nombre total de saisies | saisies | 1049.20 | 1482.10 | +41.3 % |
| Éléments potentiellement non documentés | éléments | 0.00 | 21.80 | +21.80 |
| Durée moyenne de parcours | min | 257.37 | 267.67 | +4.0 % |
| Attente moyenne de ressources par étape | min | 6.92 | 7.70 | +11.3 % |
| Taux d'occupation des salles (temps patient / temps d'ouverture) | % | 52.06 | 52.18 | +0.2 % |
| Cas programmés sortant de salle après la fermeture | % | 1.76 | 2.13 | +21.4 % |
| Cas déprogrammés le jour même (règle de fin) | cas | 0.70 | 1.80 | +157.1 % |
| Attente moyenne d'un poste informatique | min | 0.00 | 0.00 | 0.00 |
| Pic d'utilisateurs simultanés du logiciel | utilisateurs | 0.00 | 4.00 | +4.00 |
| Temps de documentation – chirurgien | h | 25.65 | 76.62 | +198.7 % |
| Temps de documentation – ibode | h | 16.86 | 16.31 | -3.3 % |

## Effets humains (scénario « Déploiement selon la fiche (lundi 8 h) »)

Confiance moyenne dans l'outil (0 = aucune, 1 = totale), relevée chaque semaine :

| Métier | S1 | S2 | S3 | S4 | S5 | Utilisation réelle de l'outil |
|---|---:|---:|---:|---:|---:|---:|
| chirurgien | 0.50 | 0.48 | 0.46 | 0.47 | 0.48 | 100 % |
| iade | 0.50 | 0.50 | 0.49 | 0.48 | 0.48 | non utilisateur |
| ibode | 0.50 | 0.50 | 0.49 | 0.49 | 0.48 | non utilisateur |
| mar | 0.50 | 0.49 | 0.49 | 0.48 | 0.48 | non utilisateur |

- Pannes simulées : 6.8 en moyenne (409 min au total)
- Temps moyen d'une saisie avec l'outil, semaine par semaine (courbe d'apprentissage) : 6.79 min → 6.53 min → 6.18 min → 6.09 min
*Mécanismes : aversion à la perte (une panne fait baisser la confiance environ deux fois plus qu'un usage réussi ne la fait monter), influence des collègues pondérée par l'autorité, courbe d'apprentissage. Les coefficients marqués « à calibrer » ne sont pas encore mesurés : lire ces résultats comme des tendances.*

## Frictions détectées par la simulation

| Gravité | Type | Parcours / étape | Rôle | Part des tâches | Occurrences / jour | Heures perdues / jour | Éléments à risque (sur la période) |
|---|---|---|---|---:|---:|---:|---:|
| critique | interoperabilite | 20 parcours / intervention | chirurgien | 99.1 % | 25.5 | 0.91 | 0.0 |
| critique | cardinalite | 20 parcours / intervention | chirurgien | 44.0 % | 11.3 | 0.36 | 21.8 |
| info | panne | 14 parcours / intervention | chirurgien | 0.7 % | 0.2 | 0.01 | 0.0 |
| info | adoption | 8 parcours / intervention | chirurgien | 0.1 % | 0.0 | 0.00 | 0.0 |

## Constats d'architecture
- **critique** (interoperabilite) : Aucun connecteur vers bloc ('logiciel_bloc') : les données devront être ressaisies dans le système actuel.
- **info** (interoperabilite) : Pas de connecteur direct vers DPI : le flux passera par 'logiciel_bloc'.
- **majeure** (cardinalite) : 20 parcours : 1.63 éléments en moyenne par tâche 'tracabilite_actes' pour un maximum de 1 par saisie.

## Contrôle de complétude de la fiche (agent 1)

Verdict **ANALYSABLE_AVEC_RESERVES** — confiance **faible** — obligatoires 25/25, recommandés 7/12, facultatifs 0/3.

| Champ | Statut requis | État | Raison |
|---|---|---|---|
| B6.pannes_connues — Pannes ou défauts connus | R | Inconnu | L'auteur a écrit « Inconnu ». |
| B7.accompagnement — Accompagnement | R | Inconnu | L'auteur a écrit « Inconnu ». |
| B8.risques_organisation — Risques pour l'organisation | R | Partiel | Information floue : « plusieurs » sans précision chiffrée. |
| B9.sites_utilisateurs — Sites déjà utilisateurs | R | Inconnu | L'auteur a écrit « Inconnu ». |
| B9.etudes — Études ou chiffres publiés | R | Vide | Rien n'est écrit. |
| B9.retours_soignants — Retour des soignants | R | Vide | Rien n'est écrit. |

## Conformité réglementaire et interopérabilité

Verdict **NO_GO** — conformité pondérée 79.5 %.

| Critère | Niveau | Exigence non démontrée |
|---|---|---|
| GO-01 | bloquant | Conformité RGPD et analyse d'impact (AIPD) réalisée avant déploiement |
| PER-03 | majeur | Rapport de test d'intrusion récent et plan de correctifs |

## Questions à poser à l'auteur de la fiche ou à l'éditeur
1. Quels incidents ont déjà été observés ?
2. Y a-t-il des référents dans l'équipe ou une aide sur place ?
3. Quels risques pour l'organisation (retards, surcharge, dépendances) ?
4. Quels établissements l'utilisent déjà ?
5. Existe-t-il des études publiées (référence complète) ?
6. Que disent les soignants qui l'utilisent, en positif et en négatif ?

## Hypothèses faites pour l'analyse
- Durées « avec le logiciel » issues de l'éditeur seul : incertitude élargie (de -25 % à +50 %).
- « Tracer les actes de l'intervention » : 0.5 min annoncées par l'éditeur, simulées entre 0.375 et 0.75 min.

## Conditions de déploiement recommandées
- Conditionner le déploiement au développement du connecteur manquant (via l'EAI).
- Exiger de l'éditeur la saisie de plusieurs éléments par fiche, ou chiffrer le temps perdu avant signature.

## Détail du score

| Motif | Points |
|---|---:|
| Exigence bloquant non démontrée : Conformité RGPD et analyse d'impact (AIPD) réalisée avant déploiement (GO-01) | -10.0 |
| Exigence majeur non démontrée : Rapport de test d'intrusion récent et plan de correctifs (PER-03) | -4.0 |
| Friction interoperabilite (critique) — 20 parcours/intervention | -20.0 |
| Friction cardinalite (critique) — 20 parcours/intervention | -20.0 |
| NO_GO réglementaire : score plafonné à 40 | 0.0 |

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
| Attente moyenne de ressources par étape | min | 6.92 [5.64 ; 8.19] | 7.70 [6.19 ; 9.20] |
| Cas annulés avant le bloc | cas | 144.60 [132.19 ; 157.01] | 144.60 [132.19 ; 157.01] |
| Cas déprogrammés le jour même (règle de fin) | cas | 0.70 [-0.65 ; 2.05] | 1.80 [-1.78 ; 5.38] |
| Cas programmés | cas | 866.00 [829.45 ; 902.55] | 866.00 [829.45 ; 902.55] |
| Confiance moyenne dans l'outil – cardiologue | 0-1 | 0.00 [0.00 ; 0.00] | 0.35 [0.30 ; 0.39] |
| Confiance moyenne dans l'outil – chir_gynecologie | 0-1 | 0.00 [0.00 ; 0.00] | 0.47 [0.43 ; 0.51] |
| Confiance moyenne dans l'outil – chir_ophtalmologie | 0-1 | 0.00 [0.00 ; 0.00] | 0.48 [0.45 ; 0.51] |
| Confiance moyenne dans l'outil – chir_orl | 0-1 | 0.00 [0.00 ; 0.00] | 0.43 [0.39 ; 0.48] |
| Confiance moyenne dans l'outil – chir_orthopedie | 0-1 | 0.00 [0.00 ; 0.00] | 0.49 [0.46 ; 0.52] |
| Confiance moyenne dans l'outil – chir_urologie | 0-1 | 0.00 [0.00 ; 0.00] | 0.47 [0.43 ; 0.51] |
| Confiance moyenne dans l'outil – chir_visceral | 0-1 | 0.00 [0.00 ; 0.00] | 0.49 [0.45 ; 0.52] |
| Confiance moyenne dans l'outil – endoscopiste | 0-1 | 0.00 [0.00 ; 0.00] | 0.47 [0.43 ; 0.51] |
| Confiance moyenne dans l'outil – iade | 0-1 | 0.00 [0.00 ; 0.00] | 0.48 [0.47 ; 0.50] |
| Confiance moyenne dans l'outil – ibode | 0-1 | 0.00 [0.00 ; 0.00] | 0.48 [0.47 ; 0.50] |
| Confiance moyenne dans l'outil – mar | 0-1 | 0.00 [0.00 ; 0.00] | 0.48 [0.47 ; 0.50] |
| Contrôle d'ubiquité (doit rester à 0) | violations | 0.00 [0.00 ; 0.00] | 0.00 [0.00 ; 0.00] |
| Dépassement horaire moyen par jour et par service | min | 247.24 [231.25 ; 263.23] | 250.90 [238.79 ; 263.01] |
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
| Durée médiane d'occupation de salle – urg_cardiologie | min | 21.22 [1.55 ; 40.90] | 17.84 [-0.35 ; 36.03] |
| Durée médiane d'occupation de salle – urg_chirurgie_generale_et_digestive | min | 113.85 [106.66 ; 121.04] | 117.30 [110.62 ; 123.98] |
| Durée médiane d'occupation de salle – urg_chirurgie_orl | min | 98.04 [81.09 ; 114.98] | 91.31 [69.33 ; 113.29] |
| Durée médiane d'occupation de salle – urg_chirurgie_orthopedique | min | 114.78 [111.33 ; 118.24] | 111.17 [104.97 ; 117.37] |
| Durée médiane d'occupation de salle – urg_chirurgie_urologique | min | 86.72 [80.49 ; 92.95] | 84.98 [77.14 ; 92.82] |
| Durée médiane d'occupation de salle – urg_endoscopie_digestive | min | 36.01 [14.11 ; 57.90] | 34.63 [20.33 ; 48.92] |
| Durée médiane d'occupation de salle – urg_gynecologie_obstetrique | min | 62.77 [55.49 ; 70.05] | 64.37 [57.85 ; 70.88] |
| Durée médiane d'occupation de salle – urg_stomatologie | min | 24.40 [-3.72 ; 52.51] | 30.89 [-6.47 ; 68.25] |
| Durée médiane d'occupation de salle – urg_visceral_robot | min | 190.23 [115.16 ; 265.29] | 228.44 [147.75 ; 309.13] |
| Durée moyenne de parcours | min | 257.37 [247.38 ; 267.35] | 267.67 [254.86 ; 280.47] |
| Durée moyenne de parcours – prog_cardiologie | min | 34.98 [-18.25 ; 88.21] | 40.34 [-21.09 ; 101.77] |
| Durée moyenne de parcours – prog_chirurgie_generale_et_digestive | min | 273.28 [268.31 ; 278.26] | 282.69 [278.72 ; 286.66] |
| Durée moyenne de parcours – prog_chirurgie_orl | min | 250.11 [243.01 ; 257.22] | 253.48 [245.69 ; 261.27] |
| Durée moyenne de parcours – prog_chirurgie_orthopedique | min | 256.87 [250.01 ; 263.74] | 265.04 [257.20 ; 272.89] |
| Durée moyenne de parcours – prog_chirurgie_urologique | min | 242.94 [236.64 ; 249.25] | 250.43 [241.33 ; 259.53] |
| Durée moyenne de parcours – prog_endoscopie_digestive | min | 184.50 [177.94 ; 191.05] | 192.97 [186.11 ; 199.82] |
| Durée moyenne de parcours – prog_gynecologie_obstetrique | min | 208.81 [198.97 ; 218.65] | 218.19 [207.99 ; 228.38] |
| Durée moyenne de parcours – prog_ophtalmologie | min | 141.63 [128.35 ; 154.92] | 151.63 [139.13 ; 164.13] |
| Durée moyenne de parcours – prog_stomatologie | min | 183.69 [114.06 ; 253.31] | 190.02 [117.63 ; 262.41] |
| Durée moyenne de parcours – prog_urologie_robot | min | 556.23 [480.43 ; 632.03] | 572.45 [489.48 ; 655.42] |
| Durée moyenne de parcours – prog_visceral_robot | min | 390.35 [274.46 ; 506.24] | 396.19 [280.28 ; 512.10] |
| Durée moyenne de parcours – urg_cardiologie | min | 111.06 [-51.50 ; 273.62] | 124.57 [-60.02 ; 309.16] |
| Durée moyenne de parcours – urg_chirurgie_generale_et_digestive | min | 431.61 [389.40 ; 473.82] | 449.42 [392.09 ; 506.76] |
| Durée moyenne de parcours – urg_chirurgie_orl | min | 388.88 [299.85 ; 477.92] | 380.79 [288.84 ; 472.74] |
| Durée moyenne de parcours – urg_chirurgie_orthopedique | min | 397.89 [356.71 ; 439.07] | 413.54 [367.09 ; 459.99] |
| Durée moyenne de parcours – urg_chirurgie_urologique | min | 375.92 [333.50 ; 418.33] | 401.44 [344.34 ; 458.54] |
| Durée moyenne de parcours – urg_endoscopie_digestive | min | 472.20 [176.35 ; 768.04] | 499.74 [178.97 ; 820.52] |
| Durée moyenne de parcours – urg_gynecologie_obstetrique | min | 374.34 [304.93 ; 443.76] | 371.50 [306.88 ; 436.12] |
| Durée moyenne de parcours – urg_stomatologie | min | 73.46 [-23.36 ; 170.28] | 62.30 [-12.16 ; 136.76] |
| Durée moyenne de parcours – urg_visceral_robot | min | 566.41 [325.47 ; 807.34] | 680.63 [466.86 ; 894.39] |
| Durées négatives tirées (doit rester à 0) | cas | 0.00 [0.00 ; 0.00] | 0.00 [0.00 ; 0.00] |
| Éléments potentiellement non documentés | éléments | 0.00 [0.00 ; 0.00] | 21.80 [17.94 ; 25.66] |
| Heure médiane d'entrée du premier cas (minutes depuis minuit) | min | 510.00 [510.00 ; 510.00] | 510.00 [510.00 ; 510.00] |
| Interventions réalisées par dimanche | cas/j | 4.65 [3.81 ; 5.49] | 4.65 [3.81 ; 5.49] |
| Interventions réalisées par jeudi | cas/j | 42.62 [38.55 ; 46.70] | 42.62 [38.55 ; 46.70] |
| Interventions réalisées par lundi | cas/j | 31.48 [28.08 ; 34.87] | 31.38 [27.88 ; 34.87] |
| Interventions réalisées par mardi | cas/j | 31.60 [29.18 ; 34.02] | 31.52 [29.08 ; 33.97] |
| Interventions réalisées par mercredi | cas/j | 34.25 [31.22 ; 37.28] | 34.23 [31.18 ; 37.27] |
| Interventions réalisées par samedi | cas/j | 5.60 [4.52 ; 6.68] | 5.60 [4.52 ; 6.68] |
| Interventions réalisées par vendredi | cas/j | 29.98 [26.49 ; 33.46] | 29.90 [26.49 ; 33.31] |
| Jours d'activité simulés | jours | 28.00 [28.00 ; 28.00] | 28.00 [28.00 ; 28.00] |
| minutes_de_panne |  | 0.00 [0.00 ; 0.00] | 408.99 [218.38 ; 599.60] |
| Occupation rapportée à la capacité totale (toutes salles × vacation) | % | 49.92 [47.96 ; 51.87] | 49.98 [48.18 ; 51.78] |
| Taux d'occupation des salles (temps patient / temps d'ouverture) | % | 52.06 [50.55 ; 53.57] | 52.18 [50.70 ; 53.65] |
| pannes |  | 0.00 [0.00 ; 0.00] | 6.80 [5.26 ; 8.34] |
| Patients par jour actif – prog_cardiologie | patients/j | 0.04 [-0.02 ; 0.10] | 0.04 [-0.02 ; 0.10] |
| Patients par jour actif – prog_chirurgie_generale_et_digestive | patients/j | 2.34 [2.04 ; 2.64] | 2.34 [2.04 ; 2.64] |
| Patients par jour actif – prog_chirurgie_orl | patients/j | 1.09 [0.84 ; 1.34] | 1.09 [0.84 ; 1.34] |
| Patients par jour actif – prog_chirurgie_orthopedique | patients/j | 3.17 [2.83 ; 3.51] | 3.16 [2.82 ; 3.51] |
| Patients par jour actif – prog_chirurgie_urologique | patients/j | 2.29 [1.88 ; 2.71] | 2.29 [1.87 ; 2.71] |
| Patients par jour actif – prog_endoscopie_digestive | patients/j | 4.30 [3.45 ; 5.15] | 4.29 [3.45 ; 5.14] |
| Patients par jour actif – prog_gynecologie_obstetrique | patients/j | 2.29 [1.96 ; 2.62] | 2.28 [1.95 ; 2.61] |
| Patients par jour actif – prog_ophtalmologie | patients/j | 4.04 [3.37 ; 4.70] | 4.03 [3.36 ; 4.70] |
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
| Patients pris en charge (parcours terminés) | patients | 720.70 [691.60 ; 749.80] | 719.60 [690.17 ; 749.03] |
| Pic d'utilisateurs simultanés du logiciel | utilisateurs | 0.00 [0.00 ; 0.00] | 4.00 [4.00 ; 4.00] |
| Nombre total de saisies | saisies | 1049.20 [1004.07 ; 1094.33] | 1482.10 [1421.79 ; 1542.41] |
| Taux d'annulation | % | 16.67 [15.58 ; 17.76] | 16.67 [15.58 ; 17.76] |
| Cas programmés sortant de salle après la fermeture | % | 1.76 [1.36 ; 2.16] | 2.13 [1.64 ; 2.63] |
| Taux d'utilisation effective de l'outil – cardiologue | % | 0.00 [0.00 ; 0.00] | 50.00 [12.30 ; 87.70] |
| Taux d'utilisation effective de l'outil – chir_gynecologie | % | 0.00 [0.00 ; 0.00] | 99.77 [99.43 ; 100.11] |
| Taux d'utilisation effective de l'outil – chir_ophtalmologie | % | 0.00 [0.00 ; 0.00] | 99.77 [99.24 ; 100.29] |
| Taux d'utilisation effective de l'outil – chir_orl | % | 0.00 [0.00 ; 0.00] | 99.52 [98.80 ; 100.24] |
| Taux d'utilisation effective de l'outil – chir_orthopedie | % | 0.00 [0.00 ; 0.00] | 99.67 [99.10 ; 100.25] |
| Taux d'utilisation effective de l'outil – chir_urologie | % | 0.00 [0.00 ; 0.00] | 100.00 [100.00 ; 100.00] |
| Taux d'utilisation effective de l'outil – chir_visceral | % | 0.00 [0.00 ; 0.00] | 99.91 [99.71 ; 100.11] |
| Taux d'utilisation effective de l'outil – endoscopiste | % | 0.00 [0.00 ; 0.00] | 100.00 [100.00 ; 100.00] |
| Temps total consacré à la documentation | h | 42.51 [40.66 ; 44.36] | 92.92 [89.39 ; 96.46] |
| Temps de documentation – cardiologue | h | 0.06 [0.00 ; 0.12] | 0.18 [-0.02 ; 0.37] |
| Temps de documentation – chir_gynecologie | h | 3.07 [2.69 ; 3.45] | 9.08 [8.06 ; 10.11] |
| Temps de documentation – chir_ophtalmologie | h | 4.01 [3.37 ; 4.66] | 12.16 [10.33 ; 14.00] |
| Temps de documentation – chir_orl | h | 1.60 [1.26 ; 1.93] | 4.72 [3.70 ; 5.73] |
| Temps de documentation – chir_orthopedie | h | 5.04 [4.51 ; 5.56] | 14.80 [13.12 ; 16.48] |
| Temps de documentation – chir_urologie | h | 3.19 [2.69 ; 3.69] | 9.63 [8.04 ; 11.22] |
| Temps de documentation – chir_visceral | h | 4.33 [3.98 ; 4.68] | 12.81 [11.76 ; 13.87] |
| Temps de documentation – endoscopiste | h | 4.36 [3.54 ; 5.18] | 13.23 [10.77 ; 15.69] |
| Temps de documentation – ibode | h | 16.86 [15.57 ; 18.14] | 16.31 [15.29 ; 17.32] |
| Temps moyen par tâche de documentation | min | 2.43 [2.40 ; 2.46] | 5.37 [5.27 ; 5.46] |
| Taux d'occupation – amplificateur | % | 5.25 [4.74 ; 5.76] | 5.34 [4.72 ; 5.96] |
| Taux d'occupation – ash | % | 6.30 [6.02 ; 6.59] | 6.37 [6.10 ; 6.64] |
| Taux d'occupation – brancardier_bloc | % | 7.36 [7.08 ; 7.64] | 7.36 [7.10 ; 7.63] |
| Taux d'occupation – brancardier_service | % | 21.83 [21.04 ; 22.61] | 21.77 [20.94 ; 22.61] |
| Taux d'occupation – cardiologue | % | 0.09 [-0.01 ; 0.19] | 0.10 [-0.01 ; 0.21] |
| Taux d'occupation – chir_gynecologie | % | 4.10 [3.52 ; 4.68] | 4.49 [3.90 ; 5.09] |
| Taux d'occupation – chir_ophtalmologie | % | 1.95 [1.63 ; 2.27] | 2.44 [2.05 ; 2.83] |
| Taux d'occupation – chir_orl | % | 4.19 [3.36 ; 5.03] | 4.42 [3.54 ; 5.30] |
| Taux d'occupation – chir_orthopedie | % | 10.59 [9.46 ; 11.72] | 11.19 [10.01 ; 12.38] |
| Taux d'occupation – chir_urologie | % | 6.73 [5.45 ; 8.00] | 7.20 [5.83 ; 8.56] |
| Taux d'occupation – chir_visceral | % | 10.97 [9.98 ; 11.96] | 11.48 [10.58 ; 12.37] |
| Taux d'occupation – colonne_coelioscopie | % | 5.79 [5.32 ; 6.27] | 6.13 [5.66 ; 6.59] |
| Taux d'occupation – echographe | % | 2.97 [2.70 ; 3.25] | 3.21 [2.90 ; 3.52] |
| Taux d'occupation – endoscopiste | % | 2.28 [1.86 ; 2.70] | 2.65 [2.16 ; 3.13] |
| Taux d'occupation – iade | % | 53.01 [51.39 ; 54.64] | 55.47 [53.93 ; 57.02] |
| Taux d'occupation – ibode | % | 33.89 [32.91 ; 34.88] | 36.52 [35.49 ; 37.56] |
| Taux d'occupation – ide_bloc | % | 24.55 [22.94 ; 26.17] | 24.33 [22.77 ; 25.88] |
| Taux d'occupation – ide_sspi | % | 0.00 [0.00 ; 0.00] | 0.00 [0.00 ; 0.00] |
| Taux d'occupation – ide_sspi_place | % | 11.41 [10.78 ; 12.05] | 11.25 [10.70 ; 11.80] |
| Taux d'occupation – lit_sspi | % | 6.25 [5.90 ; 6.59] | 6.16 [5.86 ; 6.46] |
| Taux d'occupation – mar | % | 19.11 [18.57 ; 19.65] | 19.16 [18.63 ; 19.68] |
| Taux d'occupation – mar_supervision | % | 21.16 [20.61 ; 21.70] | 21.20 [20.68 ; 21.72] |
| Taux d'occupation – microscope | % | 2.36 [2.02 ; 2.69] | 2.38 [2.07 ; 2.69] |
| Taux d'occupation – poste_preanesthesie | % | 9.33 [8.62 ; 10.04] | 10.14 [9.36 ; 10.92] |
| Taux d'occupation – poste_salle | % | 0.36 [0.34 ; 0.37] | 1.06 [1.02 ; 1.11] |
| Taux d'occupation – robot | % | 5.33 [4.12 ; 6.54] | 5.45 [4.28 ; 6.61] |
| Taux d'occupation – salle_op | % | 62.08 [60.05 ; 64.11] | 64.93 [62.97 ; 66.90] |

---
*Méthode : jumeau numérique du bloc opératoire (simulation à événements discrets et à agents), scénarios « sans outil » et « avec outil » sur les mêmes patients, graine 42. Blocapta aide à décider : il ne remplace ni l'avis des soignants ni un essai réel. Les chiffres du texte sont vérifiés automatiquement contre les résultats de simulation.*
