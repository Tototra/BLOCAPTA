# Facteur humain (modèle MOBO)

Chaque soignant concerné par l'outil est un **agent** : les utilisateurs de l'outil, et l'équipe de bloc
dont le travail change sans toucher le logiciel (chirurgiens, MAR, IADE, IBODE).

## Mécanismes

| Mécanisme | Formule | Source | Paramètre |
|---|---|---|---|
| Aversion à la perte | δ = résultat − T ; ΔT = α·δ si δ ≥ 0, α·λ·δ si δ < 0 | Kahneman et Tversky (1979, 1992) | λ = 1,955 (méta-analyse 2024), réglable de 1,8 à 2,25 |
| Diffusion en réseau | ΔT_i = κ · Σ_j w_ij (T_j − T_i), chaque jour | Rogers (1962), Bass (1969), Dilucchio et al. (2024) | κ à calibrer |
| Gradient d'autorité | w_ij ∝ autorité de j, × 2 dans la même équipe | Edmondson (2003) | chirurgien 3, MAR 2,5, IADE et IBODE 1 |
| Apprentissage | temps × (1 + (f₀ − 1) · 0,5^(usages / n½)) | courbe d'expérience | f₀ = 1,6 ; n½ = 15 (à calibrer) |
| Contournement | sous un seuil de confiance, probabilité de revenir à l'ancien processus | — | seuil 0,3 (à calibrer) |

Résultat d'un usage : 1 (succès), 0,6 (usage avec friction : double saisie, saisies multiples), 0 (panne).
Une panne est perçue par toute l'équipe utilisatrice présente ; avec le support de l'éditeur sur site,
elle est raccourcie de moitié et perçue comme moins grave (0,4). Pour un non-utilisateur, une panne est
neutre : sa confiance n'évolue que par l'influence de ses collègues.

## Pannes

- Aléatoires, selon la disponibilité annoncée dans la fiche (bloc 6) : durée moyenne 60 min (à calibrer).
- Programmées dans un scénario (`incidents`).
- Pendant une panne : mode dégradé (+30 % de temps) puis resaisie dans le logiciel.

## Scénarios (cahier des charges)

```yaml
name: Chirurgien senior réticent
human:
  kappa: 0.08
  overrides:
    - { pool: chir_orthopedie, index: 0, label: chirurgien senior réticent,
        initial_trust: 0.1, authority: 6, alpha: 0.02 }
```

Les tests de cohérence (test n° 2 du cahier des charges, `tests/test_human.py`) vérifient :

- une perte fait baisser la confiance λ fois plus qu'un gain équivalent ne la fait monter ;
- une panne précoce réduit durablement la confiance, moins avec un support sur site ;
- un sceptique influent freine son équipe ; un champion compense ;
- le temps de saisie diminue avec l'expérience ;
- l'outil n'est jamais utilisé avant sa date de déploiement.

## Lecture des résultats

Les coefficients α, κ, la confiance initiale et le seuil de contournement ne sont pas mesurés : ils sont
affichés « à calibrer » dans chaque rapport. Les résultats humains se lisent comme des **tendances et des
comparaisons entre scénarios**, pas comme des prédictions chiffrées.
