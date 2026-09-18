"""
Éléments communs à tous les modules /data_sources/<sport>.py :
- schéma de colonnes normalisé partagé entre sports
- dataclass Metric utilisée pour peupler les sélecteurs X/Y du dashboard
- petits utilitaires (normalisation de noms pour les jointures, cache parquet)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import re

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from unidecode import unidecode
except ImportError:  # dépendance optionnelle mais recommandée (accents FR/ES/serbes...)
    def unidecode(s: str) -> str:
        return s


# Racine du cache local, partagée par tous les sports.
CACHE_ROOT = Path(__file__).resolve().parent.parent / "data_cache"
RAW_ROOT = CACHE_ROOT / "raw"
PROCESSED_ROOT = CACHE_ROOT / "processed"

# Colonnes garanties présentes (éventuellement à NaN) dans le DataFrame
# retourné par get_player_stats(season) de n'importe quel sport. Un sport
# peut ajouter des colonnes supplémentaires spécifiques (ex: PER pour NBA),
# mais le dashboard ne doit compter que sur ce socle + le catalogue METRICS
# du sport pour savoir quoi afficher.
COMMON_COLUMNS = [
    "sport",       # ex "nba"
    "season",      # ex "2023-24"
    "player",      # nom affiché
    "team",        # abréviation ou nom d'équipe
]


@dataclass(frozen=True)
class Metric:
    """Une métrique sélectionnable dans les listes déroulantes X / Y du dashboard."""

    key: str            # nom de colonne dans le DataFrame
    label: str           # libellé affiché dans l'UI
    fmt: str = ",.1f"    # format d'affichage (style Python format-spec)
    category: str = "Volume"  # regroupement dans l'UI: Volume / Efficacité / Salaire / Valeur


def normalize_name(name: str) -> str:
    """Clé de jointure robuste pour matcher un même joueur entre deux sources
    (accents, casse, points, suffixes Jr./Sr./III...)."""
    if not isinstance(name, str):
        return ""
    n = unidecode(name).lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", n)
    n = re.sub(r"[^a-z\s]", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


SCHEMA_VERSION_COL = "_schema_version"


def read_cache(path: Path, schema_version: int | None = None) -> pd.DataFrame | None:
    """Lit un cache parquet, ou None si absent. Si `schema_version` est fourni,
    le cache est aussi invalidé (traité comme absent) quand la version stockée
    ne correspond pas — ça évite qu'un changement de code (ex: nouvelle colonne
    calculée) laisse silencieusement un vieux cache incomplet en place tant que
    personne ne clique sur "Rafraîchir". Un cache écrit avant l'introduction du
    versionnement (pas de colonne `_schema_version`) est aussi traité comme
    invalide dès qu'un `schema_version` est demandé."""
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if schema_version is not None:
        cached_version = df[SCHEMA_VERSION_COL].iloc[0] if SCHEMA_VERSION_COL in df.columns and len(df) else None
        if cached_version != schema_version:
            return None
    # _schema_version est un détail d'implémentation interne au cache, pas une donnée — sans ce
    # drop, elle fuit dans le DataFrame retourné à l'appelant. Repéré en testant : deux résultats
    # tous deux chargés depuis un cache (ex: nba_api stats + fiabilité) portent alors chacun leur
    # propre colonne `_schema_version`, et les fusionner (`.merge()`) plante avec une collision de
    # noms de colonnes — invisible tant qu'au moins un des deux venait d'un calcul frais.
    if SCHEMA_VERSION_COL in df.columns:
        df = df.drop(columns=SCHEMA_VERSION_COL)
    return df


def write_cache(df: pd.DataFrame, path: Path, schema_version: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if schema_version is not None:
        df = df.copy()
        df[SCHEMA_VERSION_COL] = schema_version
    df.to_parquet(path, index=False)


@dataclass(frozen=True)
class FittedValueModel:
    """Modèle salaire ~ performance déjà ajusté (voir fit_value_model), réutilisable TEL QUEL par
    apply_value_model sur un autre jeu de valeurs des MÊMES features, sans réajustement — ex. :
    data_sources/nba.py applique le modèle ajusté sur la saison régulière (échantillon fiable)
    aux valeurs playoffs d'un joueur (échantillon playoffs seul trop petit et biaisé — vers les
    franchises qui vont loin en séries — pour un nouvel ajustement fiable, voir le diagnostic de
    faisabilité playoffs). Même principe que l'application déjà existante du modèle aux rookies :
    ajusté sur un sous-groupe fiable, appliqué à tout le monde."""

    model: object  # sklearn.linear_model.LinearRegression (pas importé en tête de module base.py)
    feature_cols: list[str]
    r2: float
    n_fit: int
    residual_std: float
    # Résidus BRUTS (réel - prédit, non plafonnés) de l'échantillon de fit, mêmes unités que
    # salary_col -- exposés (pas seulement leur écart-type) pour que l'appelant puisse en tirer
    # médiane/quartiles (voir apply_value_model) sans recalculer une approximation à partir des
    # colonnes déjà plafonnées à 0 du DataFrame final.
    residuals: np.ndarray


def fit_value_model(
    df: pd.DataFrame,
    salary_col: str,
    performance_cols: list[str],
    fit_mask: pd.Series | None = None,
    min_samples: int = 15,
) -> FittedValueModel | None:
    """Ajuste (sans encore l'appliquer — voir apply_value_model) le modèle salaire ~ performance
    par régression linéaire, sur les lignes où `salary_col` et toutes les `performance_cols` sont
    renseignés (éventuellement restreint par `fit_mask`, ex. pour exclure rookies/faibles
    échantillons). Retourne None (avec un warning logué, jamais d'exception) si les colonnes
    nécessaires manquent ou si moins de `min_samples` lignes valides sont disponibles."""
    feature_cols = [c for c in performance_cols if c in df.columns]
    missing = set(performance_cols) - set(feature_cols)
    if missing:
        logger.warning("fit_value_model: colonnes de performance absentes du DataFrame : %s", missing)
    if not feature_cols or salary_col not in df.columns:
        return None

    valid = df[salary_col].notna() & df[feature_cols].notna().all(axis=1)
    fit_rows = valid if fit_mask is None else (valid & fit_mask.reindex(df.index, fill_value=False))
    n_fit = int(fit_rows.sum())
    if n_fit < min_samples:
        logger.warning(
            "fit_value_model: seulement %d ligne(s) valide(s) (< min_samples=%d), modèle non ajusté.",
            n_fit, min_samples,
        )
        return None

    from sklearn.linear_model import LinearRegression

    X_fit = df.loc[fit_rows, feature_cols].to_numpy(dtype=float)
    y_fit = df.loc[fit_rows, salary_col].to_numpy(dtype=float)
    model = LinearRegression()
    model.fit(X_fit, y_fit)
    r2 = model.score(X_fit, y_fit)
    # Marge d'incertitude du modèle : écart-type des résidus (réel - prédit) sur ce même
    # échantillon de fit. ddof=1 (estimateur non biaisé) — n_fit >= min_samples donc n-1 > 0.
    residuals_fit = y_fit - model.predict(X_fit)
    residual_std = float(np.std(residuals_fit, ddof=1))
    return FittedValueModel(
        model=model, feature_cols=feature_cols, r2=r2, n_fit=n_fit, residual_std=residual_std,
        residuals=residuals_fit,
    )


def apply_value_model(
    df: pd.DataFrame,
    fitted: FittedValueModel | None,
    salary_col: str,
    expected_col: str = "expected_salary",
    value_added_col: str = "value_added",
) -> pd.DataFrame:
    """Applique un FittedValueModel déjà ajusté (voir fit_value_model) à `df` — `df` peut être un
    DataFrame DIFFÉRENT de celui utilisé pour l'ajustement (voir FittedValueModel). Prédit
    `expected_col` pour toute ligne où les features du modèle sont renseignées, même hors de
    l'échantillon de fit d'origine (rookies, échantillon court, ou ici saison/période
    différente), plafonné à 0 (une régression linéaire peut prédire un salaire négatif pour les
    très faibles performances). `value_added_col` = expected - réel là où les deux existent.
    Ajoute aussi les colonnes constantes de diagnostic `{value_added_col}_r2/_n_fit/
    _residual_std/_residual_median/_residual_q1/_residual_q3` (reprises/dérivées de `fitted`,
    médiane et quartiles calculés sur `fitted.residuals` — les résidus BRUTS de l'échantillon de
    fit, pas une approximation recalculée après coup sur des valeurs déjà plafonnées à 0).
    `fitted=None` (modèle non ajustable, voir fit_value_model) -> toutes ces colonnes à NaN, pas
    de crash."""
    result = df.copy()
    r2_col = f"{value_added_col}_r2"
    n_fit_col = f"{value_added_col}_n_fit"
    residual_std_col = f"{value_added_col}_residual_std"
    residual_median_col = f"{value_added_col}_residual_median"
    residual_q1_col = f"{value_added_col}_residual_q1"
    residual_q3_col = f"{value_added_col}_residual_q3"
    result[expected_col] = np.nan
    result[value_added_col] = np.nan
    result[r2_col] = np.nan
    result[n_fit_col] = 0
    result[residual_std_col] = np.nan
    result[residual_median_col] = np.nan
    result[residual_q1_col] = np.nan
    result[residual_q3_col] = np.nan

    if fitted is None:
        return result

    predict_rows = result[fitted.feature_cols].notna().all(axis=1)
    X_pred = result.loc[predict_rows, fitted.feature_cols].to_numpy(dtype=float)
    predicted = np.clip(fitted.model.predict(X_pred), a_min=0, a_max=None)
    result.loc[predict_rows, expected_col] = predicted

    have_both = predict_rows & result[salary_col].notna()
    result.loc[have_both, value_added_col] = (
        result.loc[have_both, expected_col] - result.loc[have_both, salary_col]
    )
    result[r2_col] = fitted.r2
    result[n_fit_col] = fitted.n_fit
    result[residual_std_col] = fitted.residual_std
    result[residual_median_col] = float(np.median(fitted.residuals))
    result[residual_q1_col] = float(np.percentile(fitted.residuals, 25))
    result[residual_q3_col] = float(np.percentile(fitted.residuals, 75))
    return result


def compute_value_added(
    df: pd.DataFrame,
    salary_col: str,
    performance_cols: list[str],
    expected_col: str = "expected_salary",
    value_added_col: str = "value_added",
    fit_mask: pd.Series | None = None,
    min_samples: int = 15,
) -> pd.DataFrame:
    """Estime un "salaire attendu" par régression linéaire (salaire ~ stats de
    performance) et en déduit une valeur ajoutée par joueur. Générique à tout
    sport : ne connaît que des noms de colonnes, pas de logique NBA/rugby/etc.
    Réutilisable tel quel par n'importe quel data_sources/<sport>.py.

    Ajuste le modèle sur `df` PUIS l'applique à `df` (compose fit_value_model +
    apply_value_model, voir leurs docstrings pour le détail des paramètres/comportement) — pour
    ajuster sur un DataFrame et appliquer le résultat à un AUTRE (ex. modèle saison régulière
    appliqué à des valeurs playoffs), utiliser ces deux fonctions séparément plutôt que celle-ci.
    """
    fitted = fit_value_model(df, salary_col, performance_cols, fit_mask=fit_mask, min_samples=min_samples)
    return apply_value_model(df, fitted, salary_col, expected_col=expected_col, value_added_col=value_added_col)
