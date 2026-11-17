# Données attendues de l'hôpital

## 1. Journal d'événements horodatés (calibration)

Une ligne par événement, CSV ou Excel :

| Colonne pivot | Obligatoire | Exemple | Description |
|---|---|---|---|
| `case_id` | oui | `S2026-004512` | Identifiant pseudonymisé du séjour / passage |
| `activity` | oui | `depose_bloc` | Étape franchie |
| `timestamp` | oui | `2026-01-05 08:42:10` | Date-heure (ISO ou format français JJ/MM/AAAA) |
| `resource` | non | `BR04` | Agent ou équipement (pseudonymisé) |
| `role` | non | `brancardier` | Rôle de l'agent |
| `pathway` | non | `chirurgie_programmee` | Parcours, si plusieurs dans le même fichier |

Les noms réels des colonnes sont déclarés dans un fichier de correspondance :

```yaml
# mapping.yaml
case_id: IEP
activity: Libellé étape
timestamp: Date heure
resource: Matricule brancardier
timestamp_format: null   # ex. "%d/%m/%Y %H:%M" si l'inférence échoue
dayfirst: true
```

```bash
blocapta calibrate export.csv --mapping mapping.yaml --pathway chirurgie_programmee --service bloc
```

Exemple d'événements pour le bloc : `demande_brancardage`, `prise_en_charge_brancardier`, `depose_bloc`,
`entree_salle`, `debut_intervention`, `fin_intervention`, `sortie_salle`, `arrivee_sspi`, `sortie_sspi`.
Voir `blocapta generate-log` pour un fichier synthétique au bon format.

**Recommandations** : au moins 3 mois de données ; pseudonymisation avant export (aucun nom ni INS) ;
validation par le DPO et le RSSI.

## 2. Questionnaire DSI

`blocapta template -o questionnaire.md --answers reponses.yaml` produit le questionnaire (8 sections :
établissement, bloc, RH, brancardage, documentation, SI, données, organisation et sécurité) et le fichier de
réponses à compléter. Les questions marquées obligatoires sont nécessaires à une simulation pertinente.

## 3. Fiche technique éditeur

Format libre (PDF, texte) extrait par le LLM, ou format structuré directement (voir
`examples/specs/archivactes.yaml` et le schéma JSON sur `GET /specs/schema`). L'information la plus
importante pour la simulation est le bloc `metier.points_de_contact` : tâches couvertes, rôles, **nombre
maximal d'éléments par saisie**, durée de saisie, type de poste.
