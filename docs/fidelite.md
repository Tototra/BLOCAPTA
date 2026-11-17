# Test de fidélité (cahier des charges, test n° 1)

> Le bloc simulé **sans outil** retrouve-t-il les chiffres réels ? Tant qu'un indicateur clé s'écarte de
> plus de 10 %, on ne teste aucun logiciel (règle Stop/Go de la checklist d'audit).

Commande : `blocapta fidelite --replications 10 --workers 4` (API : `POST /fidelity`).

## Résultat sur le bloc de référence — verdict GO

10 réplications de 8 semaines, graine 7. Valeurs observées : export OPROOM agrégé (janvier à octobre 2026).

| Indicateur | Observé | Simulé [IC 95 %] | Écart | Tolérance |
|---|---:|---:|---:|---|
| Interventions réalisées par jour ouvré | 32,41 | 32,33 [31,49 ; 33,16] | 0,3 % | ± 10 % |
| Taux d'annulation (%) | 15,79 | 16,18 [15,45 ; 16,90] | 2,4 % | ± 10 % |
| Taux d'occupation des salles (%) | 47 | 50,05 [48,78 ; 51,33] | 6,5 % | ± 10 % |
| Heure du premier cas (min depuis minuit) | 520 | 510 | 1,9 % | ± 10 % |
| Taux de débordement (%) | 3 | 1,88 [1,57 ; 2,18] | 1,1 pt | ± 2 pt |
| Durée médiane – Chirurgie générale et digestive | 109 | 109,4 | 0,3 % | ± 10 % |
| Durée médiane – Chirurgie ORL | 85 | 84,6 | 0,4 % | ± 10 % |
| Durée médiane – Chirurgie orthopédique | 113 | 114,1 | 1,0 % | ± 10 % |
| Durée médiane – Chirurgie urologique | 84 | 87,9 | 4,6 % | ± 10 % |
| Durée médiane – Endoscopie digestive | 35 | 35,1 | 0,3 % | ± 10 % |
| Durée médiane – Gynécologie obstétrique | 60 | 58,8 | 2,0 % | ± 10 % |
| Durée médiane – Ophtalmologie | 17 | 17,1 | 0,7 % | ± 10 % |
| Durée médiane – Stomatologie | 91 | 93,4 | 2,6 % | ± 10 % |

Contrôles physiques (checklist « bug catching ») : **0** violation d'ubiquité, **0** durée négative,
occupation toujours comprise entre 0 et 100 %.

## Comment le bloc est reproduit

| Élément | Source | Mise en œuvre |
|---|---|---|
| Volumes par jour de semaine | OPROOM | ouverture des salles corrélée au jour (le jeudi ouvre plus de salles) |
| Ouverture des salles | OPROOM (jours avec activité par salle) | tirage quotidien, 63,7 % en moyenne |
| Programme opératoire | — | chaque salle ouverte reçoit une spécialité (au prorata du temps de salle) et est remplie ; un cas est programmé s'il **commence** dans la vacation (pas de biais vers les cas courts) |
| Durées par spécialité | OPROOM (centiles) | loi « quantiles » : fonction de répartition inverse des centiles observés |
| Annulations | OPROOM par spécialité | rapportées au seul programmé |
| Urgences | OPROOM (22 % des cas, profil horaire) | 24h/24, prioritaires, salle de garde la nuit |
| Effectifs et horaires | Document « Liste ressources humaines et horaires » | équipes par plage ; IADE et IBODE liés aux salles ouvertes (1 par salle) |
| MAR | SFAR / CNP ARMPO 2024 | une induction à la fois, au plus 2 patients supervisés |
| SSPI | CSP D6124-101 | lits **et** personnel présent |
| Remise en état | OPROOM (médiane 7 min) | bionettoyage en parallèle du transfert |
| Règle de fin | règles de réalisme | plus de cas programmé démarré après 18 h (déprogrammation) |

## Points d'attention

- **Taux d'occupation** : avec 32,4 cas/jour d'environ 80 min, le temps de salle rapporté aux seules salles
  ouvertes donnerait environ 65 %. Le taux OPROOM de 47 % semble rapporté à la capacité totale (toutes les
  salles × vacation) ; c'est cette définition qui est comparée. **À confirmer avec le cadre de bloc.**
- **Débordement** : la définition exacte du taux OPROOM (part des cas ou du temps) est inconnue ; une
  tolérance absolue de 2 points est utilisée pour ce petit taux.
- Réglage calibré : `programme_fill_ratio = 0,73` (part de la vacation remplie au programme).
- Hypothèses non mesurées : listées dans `metadata.parametres_a_calibrer` du bloc de référence et dans
  chaque rapport.
