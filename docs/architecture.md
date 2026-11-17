# Architecture détaillée

## Chaîne d'agents

| Agent | Rôle | Module | Peut arrêter la chaîne |
|---|---|---|---|
| 1. Contrôle de complétude | La fiche suffit-elle pour analyser ? | `spec/completeness.py` + `data/grille_completude.yaml` | oui (`NON_ANALYSABLE`) |
| — Grille réglementaire | Exigences Go/NoGo et selon le périmètre | `spec/rules.py` + `data/criteria.yaml` | non (score plafonné à 40 si `NO_GO`) |
| 2. Normalisation | Fiche → paramètres de simulation | `spec/normalize.py` | non |
| 3. Simulation | Scénarios sans / avec outil | `simulation/engine.py`, `montecarlo.py` | non |
| 4. Effets humains | Confiance, adoption, apprentissage, pannes | `simulation/human.py` | non |
| 5. Rapport | Score, confiance, vigilance, hypothèses | `reporting/` | non |

Orchestration : `pipeline.run_audit`.

## Agent 1

- 40 champs (25 O, 12 R, 3 F) ; statuts Complet, Partiel, Vide, Inconnu, Incohérent.
- Champs critiques (`B2.acteurs`, `B4.etapes`, `B6.mode_degrade`, `B8.risques_patient`) : « Partiel » bloque.
- Contrôles de cohérence : rôles du bloc 4 présents au bloc 2 (et inversement pour les utilisateurs),
  étapes dans le périmètre, durées sourcées, gain > 50 % sans mesure sur site ni étude → « affirmation non
  étayée », promesses commerciales, disponibilité de 100 %, données personnelles (verdict
  `NON_ANALYSABLE`, donnée non recopiée).
- Verdict et confiance selon les règles de la spécification ; 10 questions au plus, classées ; hypothèses ;
  fiche normalisée ; résumé lisible.
- Un LLM peut signaler des champs flous, des affirmations et des données personnelles ; il ne peut jamais
  rendre « complet » un champ vide.

## Moteur de simulation

- **Temps** en minutes, t = 0 un lundi à 0 h. Flux aléatoires séparés (arrivées, durées, documentation,
  ressources, annulations, facteur humain) : les scénarios sans et avec outil partagent les mêmes patients.
- **Ressources** : un `PriorityResource` par pool. La disponibilité au cours du temps (équipes par plage,
  ouverture aléatoire des salles, effectifs liés aux salles ouvertes via `follows`) est imposée par des
  jetons prioritaires ; une personne en cours de tâche termine d'abord (dépassement naturel).
- **Acquisition atomique** : une étape ne prend ses ressources que lorsqu'elles sont toutes disponibles,
  ce qui supprime les interblocages (attente circulaire). Contrôle d'ubiquité à chaque acquisition.
- **Étapes** : durée propre ou part de la durée de salle du cas (`duration_share`) ; ressources transmises
  à l'étape suivante (`carry`, ex. salle et IADE de l'installation au réveil) ; étapes détachées
  (`detached`, ex. bionettoyage pendant le transfert en SSPI) ; ressources optionnelles (équipements).
- **Programme opératoire** (`Hospital.programme`) : chaque jour, chaque salle ouverte reçoit une spécialité
  et est remplie jusqu'à la fin de vacation ; patient appelé avant l'heure prévue ; pas d'entrée en salle
  avant l'heure prévue ; règle de fin (déprogrammation après 18 h). Urgences 24h/24, prioritaires.
- **Documentation** : à la fin d'une étape, un rôle documente n éléments. Avec le logiciel :
  `ceil(n / max_par_saisie)` saisies, vérification du périmètre, des rôles, des interfaces (double saisie
  si le système actuel ne reçoit pas les données ; un support papier n'en demande pas), du poste requis,
  des horaires, de la licence, des pannes, de l'apprentissage et de la confiance (contournement).

### Frictions

| Type | Exemple |
|---|---|
| `cardinalite` | 3 actes à tracer, 1 acte par saisie → 2 saisies de plus, risque d'oubli |
| `interoperabilite` | pas de flux vers le logiciel de bloc → double saisie |
| `couverture` | le rôle qui fait la tâche n'est pas prévu par le logiciel |
| `ressource` | poste fixe requis absent, attente d'un poste |
| `disponibilite` | tâche hors de la plage de service du logiciel |
| `charge` | plus d'utilisateurs simultanés que la licence |
| `panne` | mode dégradé puis resaisie |
| `adoption` | outil contourné faute de confiance |

Les frictions sont agrégées par (type, tâche, métier) sur l'ensemble des parcours. Gravité :
critique si ≥ 1 h perdue ou ≥ 1 élément à risque par jour, interopérabilité sur ≥ 50 % des tâches ou
cardinalité sur ≥ 30 % ; majeure si ≥ 15 min par jour, ≥ 20 % des tâches, éléments à risque, ou
couverture / interopérabilité ; mineure si ≥ 2 % des tâches ; info sinon (`montecarlo._severity`).

## Bloc de référence

`reference.build_reference_bloc` combine les statistiques agrégées (`data/reference/oproom_stats.json`) et
les effectifs (`data/reference/effectifs_bloc.yaml`) : 10 salles, 20 parcours (programmé et urgences par
spécialité), phases d'intervention, pré-anesthésie, SSPI, équipements partagés, tâches de traçabilité
(actes et dispositifs médicaux). Le fichier généré `data/archetypes/bloc_reference.yaml` sert d'archétype :
un autre bloc s'en hérite avec `extends: bloc_reference`.

## Configuration multi-établissements

- Archétypes (`data/archetypes/`) et héritage `extends` ; fusion récursive, listes fusionnées sur l'`id`.
- JSON Patch avec sélecteurs : `[id=…]`, `[clé=valeur]`, `[*]`, `[*clé=valeur]`.
- LLM configurateur : consigne en langage naturel → patch revalidé, diff à valider.
- Questionnaire DSI relié à la configuration (`data/questionnaire_dsi.yaml`).

## Points d'extension

| Besoin | Où |
|---|---|
| Nouveau champ de fiche | `models/fiche.py` + `data/grille_completude.yaml` |
| Nouveau critère réglementaire | `data/criteria.yaml` |
| Nouveau type de friction | `models/results.py` + `simulation/engine.py::_document` |
| Nouveau mécanisme humain | `simulation/human.py` + `models/scenario.py` |
| Nouvelle loi de probabilité | `models/distributions.py` |
| Autre fournisseur LLM | protocole `llm.client.LLMClient` |
