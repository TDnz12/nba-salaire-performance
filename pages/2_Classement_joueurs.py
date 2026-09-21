"""
Classement des joueurs par valeur ajoutée — page séparée du dashboard principal (Dashboard.py,
qui ne change pas de comportement), voir la proposition validée. Page Streamlit indépendante
(système multi-page natif basé sur le dossier pages/ à côté de Dashboard.py), même principe que
pages/1_Radar_de_comparaison.py : exécutée du début à la fin à chaque interaction, duplique
volontairement quelques petits éléments de Dashboard.py (bloc CSS de densité, fonction de
chargement mise en cache, dict des libellés de période) plutôt que de les importer -- un fichier
de pages/ est un script Streamlit à part entière, pas un module.

MVP saison unique (pas de mode cumulé "Toutes les saisons" pour l'instant, proposition validée) :
un sélecteur Saison classique, pas le sélecteur combiné avec "Toutes les saisons (...)" de
Dashboard.py/pages/1_Radar_de_comparaison.py.

Les curseurs "Minutes par match minimum"/"Nombre de matchs joués minimum" ne sont PAS dupliqués
ici (proposition validée) : cette page relit leur valeur via st.session_state["min_minutes"]/
["min_games"], déposée par les sliders key= de Dashboard.py -- si l'utilisateur arrive ici sans
être passé par Dashboard.py dans cette session, on retombe sur les mêmes valeurs par défaut que
Dashboard.py (8.0 et 0) plutôt que de planter sur une clé absente.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data_sources import SPORTS

st.set_page_config(page_title="Classement des joueurs — Sports Analytics", page_icon="📊", layout="wide")

# Même bloc de densité que Dashboard.py/pages/1_Radar_de_comparaison.py (voir leur commentaire
# d'origine) — dupliqué ici pour la même respiration visuelle, sans dépendre d'un autre fichier.
st.markdown(
    """
    <style>
    div[data-testid="stAppViewBlockContainer"], .block-container {
        padding-top: 1.5rem !important;
    }
    div[data-testid="stAppViewBlockContainer"] h1:first-of-type {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] {
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] {
        padding-top: 0.25rem !important;
    }
    section[data-testid="stSidebar"] h1:first-of-type {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.7rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stElementContainer"] {
        margin-bottom: 0.3rem !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        margin-top: 0.4rem !important;
        margin-bottom: 0.4rem !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    section[data-testid="stSidebar"] hr {
        margin: 0.4rem 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("📊 Classement des joueurs")

# MVP : NBA uniquement, comme la page radar -- get_player_stats est le seul prérequis (contraire-
# ment au radar, pas besoin de radar_axes/compute_radar_scores ici).
sport = SPORTS["nba"]

# Même dict que Dashboard.py/pages/1_Radar_de_comparaison.py (dupliqué, voir leur docstring sur le
# retrait du mode "regular_playoffs") -- reste cohérent avec ce que "les stats" veulent dire
# ailleurs dans l'app. Pas de logique de pré-sélection/key= ici (rien ne route vers cette page
# avec une période imposée, contrairement au bouton radar) : un index=0 constant suffit, pas de
# risque de reset silencieux comme celui corrigé sur la page radar (qui venait d'un index recalculé
# à partir d'une valeur redevenant None après un pop()).
STATS_PERIOD_OPTIONS = {
    "Saison régulière": "regular",
    "Playoffs uniquement": "playoffs",
}

season = st.sidebar.selectbox(
    "Saison", options=sport.seasons,
    index=sport.seasons.index("2025-26") if "2025-26" in sport.seasons else 0,
)
stats_period_label = st.sidebar.selectbox(
    "Statistiques utilisées", options=list(STATS_PERIOD_OPTIONS.keys()), index=0,
)
stats_period = STATS_PERIOD_OPTIONS[stats_period_label]


@st.cache_data(show_spinner="Chargement des données NBA (nba_api + Kaggle)...")
def load_data(sport_key: str, season: str, period: str) -> pd.DataFrame:
    return SPORTS[sport_key].get_player_stats(season, force_refresh=False, period=period)


try:
    df = load_data(sport.key, season, stats_period)
except Exception as exc:
    st.error(f"Impossible de charger les données pour {season} : {exc}")
    st.stop()

if df.empty:
    st.warning(f"Aucune donnée disponible pour {season}.")
    st.stop()

# Poste / Équipe : multiselect vide = pas de filtre (même convention que team_filter dans
# Dashboard.py), pas une liste pré-cochée qui masquerait tout par défaut.
postes = sorted(df["position_group"].dropna().unique().tolist()) if "position_group" in df.columns else []
poste_filter = st.sidebar.multiselect("Poste", options=postes)
teams = sorted(df["team"].dropna().unique().tolist())
team_filter = st.sidebar.multiselect("Équipe", options=teams)

exclude_rookies = st.sidebar.checkbox(
    "Exclure les joueurs sous contrat rookie", value=False,
    help=(
        "Un rookie (< 4 saisons d'ancienneté) a un salaire fixé par la convention collective, "
        "pas négocié au marché — voir l'avertissement affiché sous ce panneau tant que des "
        "rookies restent dans la liste."
    ),
)

st.sidebar.caption(
    "Réutilise les filtres \"Minutes par match minimum\" et \"Nombre de matchs joués minimum\" "
    "de la sidebar du dashboard principal (Dashboard.py) — reviens dessus pour les ajuster, pas "
    "dupliqués ici."
)

st.title(f"📊 Classement des joueurs par valeur ajoutée — {season}")

# Repris de st.session_state (déposé par les sliders key="min_minutes"/"min_games" de
# Dashboard.py) — mêmes valeurs par défaut que Dashboard.py si cette page est ouverte directement
# dans une session qui n'est jamais passée par Dashboard.py (clé absente).
min_minutes = st.session_state.get("min_minutes", 8.0)
min_games = st.session_state.get("min_games", 0)

filtered = df.copy()
if "minutes_per_game" in filtered.columns:
    filtered = filtered[filtered["minutes_per_game"].fillna(0) >= min_minutes]
if "games_played" in filtered.columns:
    filtered = filtered[filtered["games_played"].fillna(0) >= min_games]
if poste_filter:
    filtered = filtered[filtered["position_group"].isin(poste_filter)]
if team_filter:
    filtered = filtered[filtered["team"].isin(team_filter)]
if exclude_rookies and "is_rookie_scale" in filtered.columns:
    filtered = filtered[~filtered["is_rookie_scale"].fillna(False)]

filtered = filtered.dropna(subset=["value_added_musd", "team"])

if filtered.empty:
    st.info(
        "Aucun joueur ne correspond aux filtres actuels (essaie de baisser \"Minutes par match "
        "minimum\"/\"Nombre de matchs joués minimum\" sur Dashboard.py, ou d'élargir "
        "Poste/Équipe)."
    )
    st.stop()

# Avertissement visible (pas dans un expander replié, proposition validée) dès qu'un rookie reste
# dans la liste affichée : le modèle salaire~performance EXCLUT les rookies de son AJUSTEMENT
# (fit_mask, voir data_sources/nba.py) mais leur applique quand même la ligne de marché ajustée
# sur les vétérans pour prédire un salaire attendu -- une forte valeur ajoutée chez un rookie ne
# veut donc pas dire "sous-payé par le marché" comme pour un vétéran (dont le salaire EST
# négocié), mais plutôt "jouerait comme un vétéran bien payé" si son salaire l'était aussi.
if "is_rookie_scale" in filtered.columns and filtered["is_rookie_scale"].fillna(False).any():
    st.warning(
        "⚠️ Cette liste inclut des joueurs sous contrat rookie scale (< 4 saisons d'ancienneté, "
        "badge \"🔰 Rookie\" ci-dessous). Un rookie est exclu de l'AJUSTEMENT du modèle "
        "salaire~performance, mais reçoit quand même un salaire attendu / une valeur ajoutée "
        "calculés à partir de la ligne de marché des VÉTÉRANS — une forte valeur ajoutée chez un "
        "rookie ne signifie donc pas \"sous-payé par le marché\" comme pour un vétéran (dont le "
        "salaire est réellement négocié), mais plutôt \"jouerait comme un vétéran bien payé\". "
        "Coche \"Exclure les joueurs sous contrat rookie\" dans la sidebar pour une lecture "
        "strictement \"marché\"."
    )

ranked = filtered.sort_values("value_added_musd", ascending=False).reset_index(drop=True)
ranked.insert(0, "Rang", range(1, len(ranked) + 1))

ranked["Échantillon"] = ranked["low_sample_size"].map(
    {True: "⚠️ Échantillon court", False: "Normal"}
) if "low_sample_size" in ranked.columns else "—"
ranked["Contrat"] = ranked["is_rookie_scale"].fillna(False).map(
    {True: "🔰 Rookie", False: ""}
) if "is_rookie_scale" in ranked.columns else ""

# % du plafond (value_added_pct_cap) volontairement pas affiché pour ce premier jet (saison
# unique uniquement) -- utile surtout pour comparer des saisons éloignées entre elles (mode
# cumulé "Toutes les saisons", pas encore implémenté ici), sans valeur ajoutée en mode saison
# unique où le $ reste plus parlant (même logique que le classement équipe).
ranked["Salaire réel (M$)"] = ranked["salary_musd"].round(2)
ranked["Salaire attendu (M$)"] = ranked["expected_salary_musd"].round(2)
ranked["Valeur ajoutée (M$)"] = ranked["value_added_musd"].round(2)

display_cols = {
    "Rang": "Rang", "player": "Joueur", "team": "Équipe", "position_group": "Poste",
    "Salaire réel (M$)": "Salaire réel (M$)", "Salaire attendu (M$)": "Salaire attendu (M$)",
    "Valeur ajoutée (M$)": "Valeur ajoutée (M$)",
    "Échantillon": "Échantillon", "Contrat": "Contrat",
}
table = ranked[list(display_cols.keys())].rename(columns={"player": "Joueur", "team": "Équipe", "position_group": "Poste"})

st.caption(
    f"{len(table)} joueur(s) — trié par valeur ajoutée décroissante (rang 1 = le plus sous-évalué "
    "par le modèle). Respecte les filtres Poste/Équipe/rookie ci-dessus, ainsi que les filtres "
    "Minutes/Matchs minimum du dashboard principal."
)
st.dataframe(table.set_index("Rang"), use_container_width=True, height=min(900, 38 * (len(table) + 1)))
