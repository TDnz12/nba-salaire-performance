# NBA Salary vs Performance Dashboard

Dashboard interactif qui croise stats de jeu et salaires NBA pour repérer les joueurs sous-payés ou surpayés par rapport à leur performance. Construit avec Streamlit, architecture pensée pour accueillir d'autres sports (rugby, foot, MMA, tennis) sans réécrire le dashboard.

**Démo en ligne :** https://nba-salary-performance-zjsvtgimwptkrtmwkbhxp7.streamlit.app

## Fonctionnalités

- Scatter plot salaire vs performance, sur 30 saisons NBA (1996-97 à 2025-26)
- Modèle de régression qui calcule un salaire attendu par joueur et une valeur ajoutée (sous-évalué / surévalué)
- Vue combinée toutes saisons, classement par équipe, badges MVP/DPOY/champion, mode saison régulière ou playoffs
- Normalisation en % du plafond salarial pour comparer des saisons éloignées dans le temps

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

> Si ton dossier de projet est synchronisé avec iCloud Drive (réglage "Bureau et Documents" sur Mac), déplace plutôt le `.venv` hors du dossier synchronisé (`python3 -m venv ~/.venvs/nom-du-projet`). iCloud a tendance à évincer les milliers de petits fichiers d'un environnement virtuel vers le cloud, ce qui peut rendre chaque lancement très lent.

## Sources de données

Les stats de jeu viennent de `nba_api` (endpoints publics de stats.nba.com, pas de clé requise). Les salaires viennent de deux datasets Kaggle, combinés automatiquement selon la saison :

| Saisons | Dataset | Détails |
|---|---|---|
| 2010-11 → aujourd'hui | ratin21/nba-player-stats-and-salaries-2010-2025 | Pas de PER dans ce dataset, remplacé par le PIE (nba_api) comme métrique d'efficacité |
| 1996-97 → 2009-10 | iampunitkmryh/nba-players-details-198518 (licence CC0) | Comble le trou non couvert par le premier dataset |

1996-97 est la première saison couverte : c'est la plus ancienne où `nba_api` renvoie des données exploitables (1995-96 renvoie 0 ligne).

### Configurer l'accès Kaggle

Deux options, gratuites :

**Automatique (recommandé)** : crée un compte Kaggle, génère un token API (Settings → API → Create New Token), place `kaggle.json` dans `~/.kaggle/`. L'app télécharge chaque dataset une fois puis le met en cache.

**Manuelle** : télécharge les CSV directement depuis les pages Kaggle et dépose-les dans `data_cache/raw/nba/manual/` (et `manual_legacy/` pour le second dataset). L'app les détecte automatiquement.

Sans configuration, le dashboard fonctionne quand même : les stats de jeu s'affichent, seules les colonnes salaire/valeur restent vides pour les saisons concernées.

### Normalisation en % du plafond salarial

Le plafond salarial NBA a été multiplié par plus de 6 entre 1996-97 (24,4 M$) et 2025-26 (154,6 M$), donc comparer des montants bruts entre saisons éloignées n'a pas grand sens. Le dashboard calcule aussi salaire, salaire attendu et valeur ajoutée en % du plafond de la saison, sélectionnables comme n'importe quelle autre métrique.

## Pré-remplir le cache

Par défaut chaque saison est calculée au premier chargement, ce qui peut être lent. Pour pré-calculer les 30 saisons à l'avance (avant une démo par exemple) :

```bash
PYTHONPATH=. python scripts/prefill_cache.py            # saisons manquantes seulement
PYTHONPATH=. python scripts/prefill_cache.py --force     # tout recalculer
```

## Architecture

```
app.py                       # UI Streamlit, ne connaît que data_sources.SPORTS
data_sources/
  base.py                     # schéma commun, cache parquet
  nba.py                      # logique spécifique NBA
data_cache/
  raw/nba/                    # fichiers bruts
  processed/nba/              # données normalisées, en cache par saison
scripts/
  prefill_cache.py
```

Ajouter un sport revient à créer `data_sources/<sport>.py` avec une fonction `get_player_stats()` et l'enregistrer dans `data_sources/__init__.py` — rien à changer dans `app.py`, le sélecteur de sport et les graphiques se construisent automatiquement à partir du registre.

## Méthodologie : le modèle de valeur ajoutée

Une régression linéaire (scikit-learn) prédit le salaire attendu d'un joueur à partir de sa performance. La différence entre salaire attendu et salaire réel donne la valeur ajoutée : positif si le joueur est sous-payé par rapport à sa perf, négatif s'il est surpayé.

Les variables retenues pour la NBA sont le PIE (Player Impact Estimate) et un indicateur "impact hors scoring" (rebonds, contres, passes, interceptions). Ce choix résulte de plusieurs itérations :

- Le PIE seul dégradait fortement le modèle et sous-estimait des joueurs comme Wembanyama, le marché récompensant davantage le scoring que ce que le PIE seul capture.
- PIE + points par match améliorait l'ajustement mais souffrait de colinéarité (les deux variables sont corrélées à ~0.74 chez les vétérans), ce qui rendait le coefficient du PIE négatif, un artefact statistique plutôt qu'un vrai signal.
- La version actuelle (PIE + impact hors scoring) règle ce problème de cohérence : sur environ 28 000 paires de vétérans où un joueur domine strictement un autre sur les deux variables, on passe de 753 violations à 1 seule. Le compromis, c'est un R² plus bas, le scoring, meilleur prédicteur brut du salaire, étant volontairement exclu.

Le modèle est ajusté séparément sur les vétérans (hors 4 premières saisons de contrat rookie, dont le salaire est fixé par convention collective) et exclut les échantillons trop courts (moins de 15 matchs joués), affichés différemment sur le graphique mais pas cachés du classement.

Détail des itérations et tests : voir [METHODOLOGY.md](METHODOLOGY.md).

### Limite connue : sous-valorisation des scoreurs purs

Un biais statistiquement significatif (p<0.05, testé sur plusieurs saisons) fait apparaître les très gros scoreurs (type Jordan, Curry) comme relativement sous-évalués par le modèle par rapport aux profils plus all-around. Trois pistes de correction ont été testées (retrait du PIE, ajout d'une variable de rating d'équipe non corrélée au poste, pondération réduite) sans succès probant : le biais persiste même sans la variable qu'on suspectait, ce qui suggère qu'il s'agit d'une vraie prime du marché au volume de scoring plutôt que d'un artefact de calcul. Un avertissement à ce sujet est affiché directement dans le dashboard.

## Limites connues

- La jointure salaire/stats se fait sur le nom du joueur normalisé, de rares homonymes peuvent ne pas matcher (ligne alors exclue automatiquement du scatter).
- Le dataset de salaires récent s'arrête à sa dernière saison couverte ; les saisons plus récentes affichent les stats mais pas le salaire tant que le dataset n'est pas mis à jour.
- Aucune métrique défensive individuelle n'a été retenue : les stats hustle disponibles via `nba_api` se sont révélées peu discriminantes (testées contre les DPOY de plusieurs saisons, sans résultat concluant).

## Stack technique

Python, Streamlit, pandas, scikit-learn, Plotly, nba_api, datasets Kaggle.
