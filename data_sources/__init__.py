"""
Registre central des sports supportés par le dashboard.

Chaque module de sport (nba.py, rugby.py, foot.py, ...) doit exposer :
    - get_player_stats(season: str, force_refresh: bool = False, period: str = "regular")
      -> pd.DataFrame — DataFrame normalisé selon le schéma commun défini dans base.py.
      `period` est optionnel (par défaut "regular", comportement historique) : pour la NBA,
      voir data_sources/nba.py pour les valeurs acceptées ("regular"/"playoffs") — un sport sans
      notion de playoffs peut ignorer ce paramètre.
    - SEASONS: list[str]  -> saisons disponibles dans le sélecteur
    - METRICS: dict[str, Metric] -> métriques sélectionnables en X/Y

Pour ajouter un sport plus tard :
    1. Créer data_sources/<sport>.py avec la même interface.
    2. L'enregistrer ci-dessous dans SPORTS.
    3. Rien à changer dans Dashboard.py : le sélecteur de sport et les listes de
       métriques/saisons se construisent automatiquement à partir de SPORTS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from . import nba


@dataclass(frozen=True)
class SportConfig:
    key: str                     # identifiant interne, ex "nba"
    label: str                   # libellé affiché dans l'UI, ex "Basketball (NBA)"
    available: bool              # False -> affiché grisé / "bientôt disponible"
    get_player_stats: Optional[Callable[..., pd.DataFrame]] = None
    seasons: Optional[list] = None
    metrics: Optional[dict] = None
    # Champion (récompense collective, pas un lauréat individuel) par saison, {season: team} --
    # optionnel : None pour un sport qui n'a pas encore cette donnée, Dashboard.py doit gérer l'absence
    # sans planter (voir badge 🏆 du classement d'équipes).
    champions_by_season: Optional[dict] = None
    # Récompenses individuelles (MVP, DPOY...) : award_badges_fn(df) -> Series de listes de codes
    # par ligne (voir nba.get_award_badges) ; award_icons/award_labels pour l'affichage. Les 3
    # optionnels ensemble (None par défaut) -- Dashboard.py doit gérer leur absence sans planter.
    award_badges_fn: Optional[Callable[[pd.DataFrame], pd.Series]] = None
    award_icons: Optional[dict] = None
    award_labels: Optional[dict] = None
    # Radar de comparaison de joueurs (voir pages/1_Radar_de_comparaison.py) : radar_axes
    # décrit les axes affichés (voir nba.RADAR_AXES pour le format), compute_radar_scores(df)
    # ajoute les colonnes radar_<key>_z/_score, radar_caveats est une liste de textes
    # d'avertissement à afficher sous le graph. Les 3 optionnels ensemble (None/[] par défaut
    # pour un sport qui n'a pas encore cette fonctionnalité) -- la page radar doit gérer leur
    # absence sans planter (même principe que award_badges_fn ci-dessus).
    radar_axes: Optional[list] = None
    compute_radar_scores: Optional[Callable[[pd.DataFrame], pd.DataFrame]] = None
    radar_caveats: Optional[list] = None


# --- Sport actif ---------------------------------------------------------
NBA = SportConfig(
    key="nba",
    label="Basketball (NBA)",
    available=True,
    get_player_stats=nba.get_player_stats,
    seasons=nba.SEASONS,
    metrics=nba.METRICS,
    champions_by_season=nba.CHAMPIONS_BY_SEASON,
    award_badges_fn=nba.get_award_badges,
    award_icons=nba.AWARD_ICONS,
    award_labels=nba.AWARD_LABELS,
    radar_axes=nba.RADAR_AXES,
    compute_radar_scores=nba.compute_radar_scores,
    radar_caveats=nba.RADAR_CAVEATS,
)

# --- Sports à venir (aucune implémentation, juste affichés "bientôt") ----
RUGBY = SportConfig(key="rugby", label="Rugby", available=False)
FOOTBALL = SportConfig(key="football", label="Football", available=False)
MMA = SportConfig(key="mma", label="MMA", available=False)
TENNIS = SportConfig(key="tennis", label="Tennis", available=False)

SPORTS: dict[str, SportConfig] = {
    s.key: s for s in [NBA, RUGBY, FOOTBALL, MMA, TENNIS]
}
