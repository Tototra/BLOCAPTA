"""LLM configurateur : transforme une consigne en langage naturel en patch validé.

Le LLM ne modifie jamais directement la configuration ni le code du moteur :
il propose des opérations JSON Patch, qui sont appliquées, revalidées
(schéma + contrôles métier) et présentées sous forme de diff pour validation humaine.
"""

from __future__ import annotations

import json

from ..llm import LLMClient
from .patching import ConfigPatch, PatchResult, apply_patch

SYSTEM = """Tu es l'assistant de configuration d'un jumeau numérique hospitalier (BLOCAPTA).
La configuration d'un hôpital est un document JSON. Tu dois proposer des opérations JSON Patch
(add / replace / remove) pour appliquer la consigne de l'utilisateur.

Règles :
- Utilise des chemins JSON Pointer. Pour les listes d'objets avec un id, utilise la forme
  /pathways[id=chirurgie_programmee]/steps[id=intervention]/duration_min
- `value_json` est la valeur encodée en JSON (ex. "12", "\\"07:30\\"", "{\\"dist\\": \\"poisson\\", \\"lam\\": 30}").
- Toutes les durées sont en minutes. Lois disponibles : fixed(value), exponential(mean), normal(mean, sd),
  lognormal(mean, sd), gamma(shape, scale), triangular(low, mode, high), uniform(low, high), poisson(lam),
  empirical(values: {valeur: proba}).
- Une ressource (pool) : {label, kind: humain|salle|poste|equipement, count, service, shift: {start, end, weekdays}, mobile}.
- Une étape : {id, label, duration_min, resources: {pool: quantité}, documentation: [...]}.
- Une tâche de documentation : {kind, role, current_system, items, time_per_entry_min, time_per_item_min, workstation}.
- Toute ressource référencée doit exister. Ne modifie que ce que la consigne demande.
- Si une information manque, fais une hypothèse raisonnable ET liste-la dans `hypotheses`.
"""


def _compact(config: dict) -> str:
    return json.dumps(config, ensure_ascii=False, separators=(",", ":"))[:40000]


def propose_patch(config: dict, instruction: str, llm: LLMClient, max_attempts: int = 3) -> tuple[ConfigPatch, PatchResult]:
    prompt = f"Configuration actuelle :\n{_compact(config)}\n\nConsigne : {instruction}"
    last: tuple[ConfigPatch, PatchResult] | None = None
    for _ in range(max_attempts):
        patch = llm.structured(prompt, ConfigPatch, system=SYSTEM)
        result = apply_patch(config, patch.operations)
        if result.ok:
            return patch, result
        last = (patch, result)
        prompt += (
            f"\n\nTa proposition précédente {patch.model_dump_json()} a échoué : {result.errors}. "
            "Corrige les opérations."
        )
    assert last is not None
    return last
