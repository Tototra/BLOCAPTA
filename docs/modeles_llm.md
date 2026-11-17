# Choix du modèle LLM (Ollama)

BLOCAPTA utilise trois rôles LLM, chacun configurable indépendamment dans `.env` :

| Rôle | Variable | Besoin |
|---|---|---|
| Extraction de fiche technique | `BLOCAPTA_MODEL_EXTRACTION` | JSON structuré fiable, bon français, contexte long (PDF) |
| Configurateur | `BLOCAPTA_MODEL_CONFIGURATOR` | Raisonnement sur une configuration JSON, JSON Patch valide |
| Rédaction du rapport | `BLOCAPTA_MODEL_REPORT` | Français professionnel, respect strict des faits |

Toutes les sorties passent par les **sorties structurées d'Ollama** (`format` = schéma JSON), puis sont
revalidées par Pydantic avec relance automatique en cas d'erreur.

## Recommandation

| Matériel | Modèle conseillé | Commande |
|---|---|---|
| Portable 16 Go RAM / GPU 8 Go (défaut) | **Qwen3 8B** | `ollama pull qwen3:8b` |
| GPU 24 Go / Mac 32 Go | Qwen 3.6 27B | `ollama pull qwen3.6:27b` |
| Préférence pour un modèle européen | Mistral Small 3.2 (24B) | `ollama pull mistral-small3.2` |

- **Qwen3 8B** est le choix par défaut : léger, très bon en sortie JSON contrainte, correct en français. Le
  « thinking » est désactivé (`BLOCAPTA_OLLAMA_THINK=false`) pour des réponses rapides et un JSON propre.
- Pour de meilleurs rapports et un configurateur plus fiable, utiliser un modèle plus gros pour
  `REPORT` et `CONFIGURATOR` et garder le 8B pour l'extraction.
- Éviter pour l'instant `gpt-oss` pour les sorties structurées strictes (problèmes de compatibilité signalés
  avec Ollama).

Vérifiez la disponibilité exacte d'un tag avec `ollama pull <tag>` : la bibliothèque Ollama évolue vite.
`blocapta config` affiche les modèles actifs et `GET /health` indique s'ils sont installés.

## Souveraineté et données de santé

Les modèles tournent **en local** via Ollama : aucune donnée ne sort de l'infrastructure de l'hôpital. Les
fiches techniques éditeurs ne contiennent pas de données patients ; les journaux de calibration doivent être
pseudonymisés en amont et ne sont **jamais** envoyés au LLM (la calibration est purement statistique).

## Brancher un autre fournisseur

Implémenter le protocole `blocapta.llm.client.LLMClient` (méthodes `structured` et `text`) et le passer aux
fonctions `run_audit`, `propose_patch`, `validate_document`.
