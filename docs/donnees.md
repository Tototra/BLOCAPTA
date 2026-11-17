# Données

## 1. Export OPROOM → bloc de référence

L'export du logiciel de bloc (une ligne par intervention : date, heure, salle, spécialité, type, durée,
annulation et motif) est la base du bloc de référence.

```bash
python tools/oproom_aggregate.py chemin/vers/OPROOM.xlsx -o src/blocapta/data/reference/oproom_stats.json
blocapta reference           # régénère data/archetypes/bloc_reference.yaml
blocapta fidelite            # vérifie que le bloc simulé retrouve les chiffres réels
```

Le script :
- **supprime les colonnes nominatives** (chirurgien, anesthésiste) avant tout calcul ;
- filtre les durées aberrantes (hors 3 à 600 min, ex. 27 400 min) ;
- ne produit que des statistiques agrégées : volumes par jour de semaine et par mois, centiles de durée
  par spécialité, annulations et motifs, part et profil horaire des urgences, ouverture des salles,
  remise en état, heure du premier cas.

Le fichier brut n'est **jamais** versionné (dossier `data/private/` ignoré par git).

Les effectifs, horaires, équipements et hypothèses non mesurées sont dans
`src/blocapta/data/reference/effectifs_bloc.yaml` (chaque valeur supposée y est marquée « à calibrer »).

## 2. Fiche logiciel (template v0.1)

Format machine du template du projet : `blocapta fiche-template -o fiche.yaml`, ou schéma JSON sur
`GET /fiches/schema`. Exemples : `examples/fiches/archivactes.yaml`, `examples/fiches/scantrace.yaml`.

Règles : des faits et des chiffres avec unités ; une source par affirmation ; « Inconnu » plutôt que vide ;
aucune donnée de patient ni nom de soignant. Le bloc 4 (processus avant / après) est le plus important :
pour chaque étape qui change, qui, quelle action, durée sans et avec le logiciel, source et niveau de preuve,
et le champ `tache_bloc` qui la relie au jumeau (`tracabilite_actes`, `tracabilite_dm`…).

Une fiche peut aussi être fournie en PDF, Word (.docx) ou texte : le LLM l'extrait vers ce format, puis
l'agent 1 la contrôle comme une fiche structurée.

## 3. Questionnaire DSI / cadre de bloc

`blocapta template -o questionnaire.md --answers reponses.yaml` produit le questionnaire (8 sections :
établissement, salles et programme, pré-anesthésie et SSPI, équipes, équipements, traçabilité et SI,
données de calibration, organisation) et le fichier de réponses. `blocapta apply-answers reponses.yaml`
applique les réponses sur le bloc de référence ; les réponses en texte libre sont confiées au LLM
configurateur (option `--llm`).

## 4. Journaux horodatés (calibration fine)

Pour calibrer un parcours détaillé (brancardage, pré-anesthésie, SSPI), un journal d'événements suffit :

| Colonne | Obligatoire | Exemple |
|---|---|---|
| `case_id` | oui | identifiant pseudonymisé du séjour |
| `activity` | oui | `entree_salle` |
| `timestamp` | oui | `2026-01-05 08:42:10` ou `05/01/2026 08:42` |
| `resource`, `role`, `pathway` | non | `BR04`, `brancardier`, `chirurgie_programmee` |

```bash
blocapta calibrate export.csv --mapping mapping.yaml --hospital mon_bloc.yaml
```

## Données manquantes à recueillir (règles de réalisme, section 15)

Horodatages complets du parcours, mode d'arrivée des patients, nombre de brancards et de postes de
pré-anesthésie, planning des équipes et des vacations, annulations du jour même, classes d'urgence et délais,
lits d'aval, équipements partagés et leur planning, affectation réelle des MAR en salle.
