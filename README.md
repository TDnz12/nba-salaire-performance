# NBA Salary vs Performance Dashboard

Dashboard interactif qui croise stats de jeu et salaires NBA, saison par saison ou sur l'historique complet. Construit avec Streamlit, architecture pensée pour accueillir d'autres sports (rugby, foot, MMA, tennis) sans réécrire le dashboard.

**Démo en ligne :** https://sportsanalyticsdashboard.streamlit.app

## Fonctionnalités

- Scatter plot salaire vs performance, sur 30 saisons NBA (1996-97 à 2025-26)
- Vue combinée toutes saisons, badges MVP/DPOY/champion, mode saison régulière ou playoffs
- Radar de comparaison entre joueurs sur un ensemble de métriques normalisées par poste
- Normalisation en % du plafond salarial pour comparer des saisons éloignées dans le temps

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run Dashboard.py
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

Sans configuration, le dashboard fonctionne quand même : les stats de jeu s'affichent, seule la colonne salaire reste vide pour les saisons concernées.

### Normalisation en % du plafond salarial

Le plafond salarial NBA a été multiplié par plus de 6 entre 1996-97 (24,4 M$) et 2025-26 (154,6 M$), donc comparer des montants bruts entre saisons éloignées n'a pas grand sens. Le dashboard calcule aussi le salaire en % du plafond de la saison, sélectionnable comme n'importe quelle autre métrique.

## Pré-remplir le cache

Par défaut chaque saison est calculée au premier chargement, ce qui peut être lent. Pour pré-calculer les 30 saisons à l'avance (avant une démo par exemple) :

```bash
PYTHONPATH=. python scripts/prefill_cache.py            # saisons manquantes seulement
PYTHONPATH=. python scripts/prefill_cache.py --force     # tout recalculer
```

## Architecture

```
Dashboard.py                 # UI Streamlit, ne connaît que data_sources.SPORTS
data_sources/
  base.py                     # schéma commun, cache parquet
  nba.py                      # logique spécifique NBA
data_cache/
  raw/nba/                    # fichiers bruts
  processed/nba/              # données normalisées, en cache par saison
scripts/
  prefill_cache.py
```

Ajouter un sport revient à créer `data_sources/<sport>.py` avec une fonction `get_player_stats()` et l'enregistrer dans `data_sources/__init__.py` — rien à changer dans `Dashboard.py`, le sélecteur de sport et les graphiques se construisent automatiquement à partir du registre.

## Méthodologie

Détail des choix de métriques, des pistes testées et abandonnées, et des limites connues : voir [METHODOLOGY.md](METHODOLOGY.md).

## Limites connues

- La jointure salaire/stats se fait sur le nom du joueur normalisé, de rares homonymes peuvent ne pas matcher (ligne alors exclue automatiquement du scatter).
- Le dataset de salaires récent s'arrête à sa dernière saison couverte ; les saisons plus récentes affichent les stats mais pas le salaire tant que le dataset n'est pas mis à jour.
- Aucune métrique défensive individuelle n'a été retenue : les stats hustle disponibles via `nba_api` se sont révélées peu discriminantes (testées contre les DPOY de plusieurs saisons, sans résultat concluant).

## Stack technique

Python, Streamlit, pandas, Plotly, nba_api, datasets Kaggle.
