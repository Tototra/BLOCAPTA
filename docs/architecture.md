# Architecture détaillée

## Flux d'un audit

1. **Fiche technique** (`spec/`) : le document de l'éditeur est lu. S'il est structuré (YAML/JSON conforme à
   `SpecSheet`), il est utilisé tel quel ; sinon le LLM d'extraction remplit le schéma avec une sortie JSON
   contrainte (`format` d'Ollama) puis revalidée par Pydantic. Les critères de `data/criteria.yaml` sont évalués
   par un moteur de règles **déterministe**. Un critère bloquant en échec stoppe l'audit avant la simulation.
2. **Conversion** : `SoftwareModel.from_spec_sheet` traduit la fiche en modèle de simulation (points de
   contact, interfaces, licence, plage de disponibilité). Le modèle peut aussi être écrit à la main.
3. **Simulation** (`simulation/`) : deux scénarios avec les mêmes arrivées de patients (flux aléatoires séparés) :
   situation actuelle et avec logiciel. N réplications, intervalles de confiance à 95 % (loi de Student).
4. **Analyse statique** : connecteurs manquants, SSO, tâches non modélisées, cardinalité moyenne.
5. **Score** (`reporting/scoring.py`) : 100 moins des pénalités explicites (fiche incomplète, frictions selon
   leur gravité, constats statiques non déjà mesurés). Plafonné à 30 si la fiche n'est pas admissible.
6. **Rédaction** : le LLM reçoit uniquement les faits JSON ; chaque nombre de son texte est vérifié
   (`factcheck.py`), sinon repli sur la rédaction déterministe.

## Le moteur de simulation

- **Temps** : minutes ; t = 0 correspond à un lundi 00:00.
- **Ressources** : un `PriorityResource` SimPy par pool. Hors horaires, un processus « jeton » réserve toutes
  les unités avec une priorité supérieure. Une personne en cours de tâche termine d'abord (pas de
  préemption), ce qui produit naturellement les dépassements horaires.
- **Parcours** : suite d'étapes. Chaque étape acquiert ses ressources (ordre alphabétique pour éviter les
  interblocages), dure selon sa loi, puis libère ses ressources. Exception : le rôle qui documente reste
  mobilisé pendant la documentation.
- **Documentation** : nombre d'éléments `n` tiré de la loi `items`.
  - Situation actuelle : `temps_par_saisie + n × temps_par_élément`.
  - Avec logiciel : `ceil(n / max_par_saisie)` saisies, puis vérification des rôles, des interfaces (double
    saisie si le système actuel ne reçoit pas les données), du poste requis, des horaires et de la licence.
- **Frictions** : chaque écart produit un `FrictionEvent` (temps perdu, éléments à risque). Elles sont ensuite
  agrégées par type, parcours, étape et rôle, avec la part des tâches touchées et une gravité.

### Règles de gravité

| Gravité | Condition (par jour d'activité) |
|---|---|
| critique | ≥ 1 h perdue/jour, ou ≥ 1 élément à risque/jour, ou interopérabilité touchant ≥ 50 % des tâches, ou cardinalité touchant ≥ 30 % des tâches |
| majeure | ≥ 15 min perdues/jour, ou ≥ 20 % des tâches, ou des éléments à risque, ou toute friction de couverture ou d'interopérabilité |
| mineure | ≥ 2 % des tâches |
| info | le reste |

Ces seuils sont dans `simulation/montecarlo.py::_severity` et sont faits pour être ajustés avec les DSI.

## Calibration et validation du jumeau

`calibration/` reconstruit la variante principale d'un parcours à partir d'un journal (une ligne par
événement), ajuste une loi sur chaque transition (lognormale, gamma, exponentielle, normale ; choix par AIC ;
test de Kolmogorov-Smirnov rapporté), estime les arrivées (loi de comptage journalière, profil horaire, jours
actifs). `simulation/validation.py` compare ensuite la simulation de l'existant aux valeurs observées :
le jumeau est considéré valide si l'écart reste sous la tolérance (10 % par défaut).

> Attention : les durées observées entre deux événements incluent déjà l'attente des ressources. Si l'on
> ajoute des ressources contraintes à une étape calibrée, la validation peut montrer une durée simulée trop
> longue. C'est précisément ce que la validation sert à révéler.

## Configurateur multi-établissements

- **Archétypes** (`data/archetypes/`) et héritage `extends` : fusion récursive des dictionnaires, listes
  fusionnées sur l'`id`, suppression via `{__delete__: true}`.
- **JSON Patch** avec sélecteurs lisibles `/pathways[id=…]/steps[id=…]`.
- **LLM configurateur** : propose des opérations (valeurs encodées en JSON pour rester compatibles avec les
  sorties structurées), relancé automatiquement en cas d'échec de validation, avec des hypothèses explicites.
  Il ne touche jamais au code du moteur.
- **Questionnaire DSI** (`data/questionnaire_dsi.yaml`) : chaque question peut cibler un chemin de
  configuration avec une transformation (`poisson`, `lognormal`, `empirical`, `time_window`…). Les réponses en
  texte libre sont confiées au LLM configurateur.

## Points d'extension

| Besoin | Où |
|---|---|
| Nouveau type de friction | `models/results.py::FrictionType` + `simulation/engine.py::_document` |
| Nouveau critère de fiche | `data/criteria.yaml` |
| Nouvelle loi de probabilité | `models/distributions.py` (+ union `Distribution`) |
| Autre fournisseur LLM | implémenter le protocole `llm.client.LLMClient` |
| Nouvel archétype | `data/archetypes/<nom>.yaml` |
