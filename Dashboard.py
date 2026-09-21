"""
Dashboard interactif de data analytics sportive — MVP Basketball (NBA).

Architecture multi-sport : ce fichier ne connaît que l'interface (Streamlit)
et le registre data_sources.SPORTS. Toute la logique spécifique à un sport
(scraping, téléchargement, normalisation, cache) vit dans /data_sources.
Ajouter le rugby/foot/MMA/tennis plus tard = créer data_sources/<sport>.py
avec la même interface et l'enregistrer dans data_sources/__init__.py.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_sources import SPORTS

st.set_page_config(page_title="Sports Analytics Dashboard", page_icon="🏀", layout="wide")

# CSS de densité : réduit les marges/espacements par défaut de Streamlit pour que le graph
# tienne à l'écran sans scroll au chargement. Purement présentationnel (aucune logique
# touchée). Cible les data-testid internes de Streamlit 1.63 — plusieurs sélecteurs
# redondants (testid + fallback classe) pour rester robuste si la version change un peu.
st.markdown(
    """
    <style>
    /* Remonte tout le contenu principal (le gros titre + le graph juste en dessous). */
    div[data-testid="stAppViewBlockContainer"], .block-container {
        padding-top: 1.5rem !important;
    }
    div[data-testid="stAppViewBlockContainer"] h1:first-of-type {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* Sidebar : espace au-dessus du titre "Sports Analytics" quasi supprimé (le premier essai
       à 1rem sur stSidebarUserContent seul ne suffisait pas — l'espace venait aussi du conteneur
       parent, donc on le réduit aux deux niveaux). */
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

    /* Sidebar : espace vertical entre chaque widget — un peu plus aéré que le premier essai
       (0.35rem), sans revenir à l'espacement par défaut de Streamlit. */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.7rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stElementContainer"] {
        margin-bottom: 0.3rem !important;
    }

    /* Titres et séparateurs de la sidebar (titre, "Filtres", lignes "---") moins espacés. */
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


# --------------------------------------------------------------------------
# Sidebar : sélection du sport / saison / métriques / filtres
# --------------------------------------------------------------------------
st.sidebar.title("🏆 Sports Analytics")

sport_keys = list(SPORTS.keys())
sport_choice_key = st.sidebar.radio(
    "Sport",
    options=sport_keys,
    format_func=lambda k: SPORTS[k].label if SPORTS[k].available else f"{SPORTS[k].label} — bientôt disponible",
    index=0,
)
sport = SPORTS[sport_choice_key]

if not sport.available:
    st.sidebar.info("Ce sport n'est pas encore disponible dans le MVP.")
    st.title(f"{sport.label}")
    st.info(
        "🚧 Ce sport arrive dans une prochaine version. "
        "Seul **Basketball (NBA)** est actif pour l'instant. "
        "L'architecture du projet (`data_sources/<sport>.py`) est déjà prête à l'accueillir."
    )
    st.stop()

# Vue combinée : charge et concatène TOUTES les saisons de sport.seasons (1996-97 ->
# 2025-26, voir data_sources/nba.SEASONS) plutôt qu'une seule. Repose sur les deux sources
# de salaires documentées dans data_sources/nba.py (ratin21 pour 2010-11+, dataset CC0
# "legacy" avant, frontière à NBA_SALARY_CAP_BY_SEASON/RATIN21_DATASET_START_YEAR) —
# transparent ici, le DataFrame retourné par get_player_stats a le même schéma quelle que
# soit la source. Un échec ponctuel sur une saison (réseau, dataset absent...) n'empêche pas
# d'afficher les autres, voir failed_seasons plus bas.
ALL_SEASONS_LABEL = f"Toutes les saisons ({sport.seasons[-1]} → {sport.seasons[0]})"
ALL_SEASONS_KEYS = list(sport.seasons)

season_options = [ALL_SEASONS_LABEL] + sport.seasons
_default_season = "2025-26" if "2025-26" in sport.seasons else sport.seasons[0]
season = st.sidebar.selectbox(
    "Saison", options=season_options, index=season_options.index(_default_season)
)
is_all_seasons = season == ALL_SEASONS_LABEL

# Statistiques utilisées (saison régulière / playoffs uniquement) : n'affecte QUE le scatter plot
# principal et le modèle qui le nourrit (voir get_player_stats(..., period=...) dans
# data_sources/nba.py pour le détail des 2 options). Volontairement limité au mode saison unique
# (complexité déjà présente en mode "Toutes les saisons" — bascule $/%, trajectoire, badges...
# voir la proposition validée) : le sélecteur disparaît entièrement plutôt que de rester affiché
# grisé/inutilisable.
#
# Un 3e mode ("Saison + Playoffs (agrégé)", period="regular_playoffs") a existé un temps puis a
# été retiré (décision explicite) : mélanger un échantillon cohérent (saison régulière, 82 matchs
# pour tout le monde) avec un échantillon non représentatif (playoffs, biaisé par qui se qualifie
# et jusqu'où) n'apportait pas assez de valeur pour la complexité que ça ajoutait. Le code qui le
# calculait (_combine_regular_playoffs_stats) a été supprimé de data_sources/nba.py -- si "regular_
# playoffs" apparaît encore quelque part (grep), c'est un oubli de ce nettoyage, pas une option
# valide.
#
# Défaut = "Saison régulière" (repassée en premier/par défaut après le retrait du mode combiné,
# qui l'avait temporairement remplacée). Même dict et même défaut dupliqués dans
# pages/1_Radar_de_comparaison.py (voir sa docstring) -- à resynchroniser à la main si cet ordre
# change à nouveau. Le futur classement joueurs (pages/2_Classement_joueurs.py) doit repartir de
# ce même ordre/défaut dès sa création. Le classement équipe plus bas N'EST PAS concerné : il
# reste volontairement figé sur "regular" en dur, indépendamment de ce sélecteur.
STATS_PERIOD_OPTIONS = {
    "Saison régulière": "regular",
    "Playoffs uniquement": "playoffs",
}
if not is_all_seasons:
    stats_period_label = st.sidebar.selectbox(
        "Statistiques utilisées", options=list(STATS_PERIOD_OPTIONS.keys()), index=0,
    )
    stats_period = STATS_PERIOD_OPTIONS[stats_period_label]
else:
    stats_period = "regular"


@st.cache_data(show_spinner="Chargement des données NBA (nba_api + Kaggle)...")
def load_data(sport_key: str, season: str, force_refresh: bool, period: str = "regular") -> pd.DataFrame:
    return SPORTS[sport_key].get_player_stats(season, force_refresh=force_refresh, period=period)


@st.cache_data(show_spinner="Chargement de l'historique complet (trajectoire joueur)...")
def load_all_seasons_data(sport_key: str, season_keys: tuple[str, ...], force_refresh: bool) -> tuple[pd.DataFrame, list]:
    """Charge et concatène TOUTES les saisons d'un coup, indépendamment de la saison
    actuellement affichée — utilisé par la trajectoire de valeur ajoutée par joueur (qui a
    besoin de l'historique complet même quand une saison unique est sélectionnée dans la
    sidebar). Mis en cache séparément de load_data() : une saison en échec ne fait pas planter
    les autres (même principe que le mode "Toutes les saisons" plus bas), juste absente du
    résultat et listée dans le 2e élément retourné.

    period="regular" volontairement EN DUR (pas paramétrable) : la trajectoire reste TOUJOURS en
    saison régulière, quel que soit le choix fait dans le sélecteur "Statistiques utilisées" de
    la sidebar — celui-ci n'agit que sur le scatter plot principal. Décision explicite, pas un
    oubli (voir aussi team_ranking_source_df un peu plus bas dans ce fichier, même principe)."""
    frames, failed = [], []
    for s in season_keys:
        try:
            frames.append(SPORTS[sport_key].get_player_stats(s, force_refresh=force_refresh, period="regular"))
        except Exception as exc:
            failed.append((s, exc))
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return combined, failed


def _handle_refresh_click() -> None:
    # Exécuté par Streamlit AVANT le re-run complet du script (callback on_click) — donc même si
    # le bouton est déclaré tout en bas de la sidebar (affiché en dernier), son effet est bien
    # pris en compte dès le chargement des données un peu plus haut dans le script.
    load_data.clear()  # sinon les autres saisons déjà en cache mémoire resteraient périmées
    st.session_state["_pending_force_refresh"] = True


# True uniquement pour le run qui suit immédiatement un clic sur "Rafraîchir" (voir le bouton,
# positionné tout en bas de la sidebar) — pop() pour ne pas rester bloqué à True indéfiniment.
force_refresh = st.session_state.pop("_pending_force_refresh", False)

if is_all_seasons:
    frames = []
    failed_seasons = []
    for s in ALL_SEASONS_KEYS:
        try:
            # period="regular" explicite (== stats_period ici de toute façon, voir plus haut) :
            # le mode "Toutes les saisons" n'a pas le sélecteur playoffs, uniquement de la saison
            # régulière.
            frames.append(load_data(sport.key, s, force_refresh, "regular"))
        except Exception as exc:  # nba_api down, pas d'internet, dataset Kaggle absent, etc.
            failed_seasons.append((s, exc))
    if not frames:
        st.error(f"Impossible de charger la moindre saison : {failed_seasons}")
        st.stop()
    df = pd.concat(frames, ignore_index=True)
    if failed_seasons:
        st.warning(
            "⚠️ Certaines saisons n'ont pas pu être chargées et sont absentes du graph : "
            + ", ".join(f"{s} ({exc})" for s, exc in failed_seasons)
        )
    # Classement d'équipes ET trajectoire : toujours en saison régulière (voir plus bas à chaque
    # section) — ici les deux confondus avec `df`, puisque df EST déjà la saison régulière dans
    # ce mode (pas de sélecteur playoffs en "Toutes les saisons").
    team_ranking_source_df = df
else:
    try:
        df = load_data(sport.key, season, force_refresh, stats_period)
    except Exception as exc:
        st.error(f"Impossible de charger les données pour {season} : {exc}")
        st.stop()
    # Le classement d'équipes reste TOUJOURS en saison régulière, quel que soit le choix fait
    # dans "Statistiques utilisées" ci-dessus (décision explicite — le sélecteur playoffs n'agit
    # QUE sur le scatter plot principal et le modèle qui le nourrit, voir aussi
    # load_all_seasons_data plus bas pour la trajectoire, même principe). Si stats_period="regular"
    # déjà, `df` EST ce dataset, pas de rechargement ; sinon un second appel à load_data (repasse
    # par le cache disque get_player_stats, pas un nouveau calcul coûteux).
    if stats_period == "regular":
        team_ranking_source_df = df
    else:
        try:
            team_ranking_source_df = load_data(sport.key, season, force_refresh, "regular")
        except Exception:
            team_ranking_source_df = df  # repli défensif (mieux qu'un crash) plutôt qu'un blocage total

if df.empty:
    st.warning(f"Aucune donnée disponible pour {season}.")
    st.stop()

metrics = sport.metrics
metric_keys = list(metrics.keys())
# Récompenses individuelles (MVP, DPOY...) : optionnelles sur SportConfig, {} en repli pour un
# sport qui ne les expose pas encore (voir data_sources/__init__.py) -- pas de crash, juste aucun
# badge affiché pour ce sport-là.
AWARD_ICONS = sport.award_icons or {}
AWARD_LABELS = sport.award_labels or {}
# Calculée sur df ENTIER (avant tout filtre minutes/matchs/équipe, voir plot_df plus bas), PAS sur
# plot_df déjà filtré : le rapprochement (nba.match_season_awards) est volontairement strict et
# lève si un lauréat connu ne matche aucun joueur du roster de sa saison -- un lauréat filtré par
# le curseur "Minutes par match minimum" (ex. un joueur de banc comme Ike Austin, MIP 1996-97)
# ferait planter l'app si le rapprochement tournait sur la liste déjà réduite. En le calculant ici
# sur le roster complet puis en laissant `plot_df = df.copy()` propager la colonne, un lauréat
# filtré disparaît normalement de l'affichage (comme n'importe quel autre joueur) sans jamais
# déclencher l'exception -- l'exception ne doit se déclencher QUE pour un vrai problème de
# rapprochement de nom, jamais à cause d'un filtre d'affichage.
df["_awards"] = (
    sport.award_badges_fn(df) if sport.award_badges_fn is not None
    else pd.Series([[] for _ in range(len(df))], index=df.index)
)


def metric_label(key: str) -> str:
    m = metrics[key]
    return f"{m.label}  ·  {m.category}"


# Ordre de la sidebar pensé par praticité d'usage : d'abord retrouver un joueur précis, puis
# choisir ce qu'on regarde (axes/couleur/taille), puis affiner (filtres), puis un réglage de
# fiabilité des données en dernier (le moins souvent utile).
st.sidebar.markdown("---")
player_options = ["Aucun"] + sorted(df["player"].dropna().unique().tolist())
searched_player = st.sidebar.selectbox(
    "🔍 Rechercher un joueur",
    options=player_options,
    index=0,
    help="Tape un nom pour filtrer la liste. Le joueur sélectionné est entouré sur le graph.",
)

def _handle_radar_click() -> None:
    # Exécuté par Streamlit avant le switch de page (callback on_click, même mécanisme que
    # _handle_refresh_click plus bas) : dépose le joueur/la saison dans st.session_state, lus
    # puis pop() par la page radar pour ne pré-sélectionner qu'une fois (même pattern que
    # _pending_force_refresh). st.switch_page ici plutôt que dans le corps du script : un
    # switch_page() appelé en dehors d'un callback interromprait immédiatement le script AVANT
    # que le reste de la sidebar (filtres, bouton Rafraîchir...) n'ait fini de s'afficher.
    st.session_state["radar_preselect_player"] = searched_player
    st.session_state["radar_preselect_season"] = None if is_all_seasons else season
    st.switch_page("pages/1_Radar_de_comparaison.py")


if searched_player != "Aucun":
    st.sidebar.button(
        "🎯 Voir le profil radar", on_click=_handle_radar_click,
        help="Ouvre la vue radar de comparaison de profils avec ce joueur pré-sélectionné.",
    )

teams = sorted(df["team"].dropna().unique().tolist())
team_filter = st.sidebar.multiselect("Filtrer par équipe (optionnel)", options=teams)

st.sidebar.markdown("---")
x_key = st.sidebar.selectbox(
    "Statistique en abscisse (X)", options=metric_keys, format_func=metric_label,
    index=metric_keys.index("salary_musd") if "salary_musd" in metric_keys else 0,
)
y_key = st.sidebar.selectbox(
    "Statistique en ordonnée (Y)", options=metric_keys, format_func=metric_label,
    index=metric_keys.index("points_per_game") if "points_per_game" in metric_keys else 1,
)

color_options = ["Aucune"] + metric_keys + (["team"] if "team" in df.columns else [])
# En mode "Toutes les saisons", le $ brut n'est pas comparable d'une saison à l'autre (le
# plafond salarial a été multiplié par ~6 entre 1996-97 et 2025-26) — on colore donc par
# défaut sur la valeur ajoutée normalisée en % du plafond plutôt qu'en M$.
if is_all_seasons:
    default_color = "value_added_pct_cap" if "value_added_pct_cap" in metric_keys else "value_added_musd"
else:
    default_color = "value_added_musd" if "value_added_musd" in metric_keys else "Aucune"
if default_color not in metric_keys:
    default_color = "Aucune"
color_key = st.sidebar.selectbox(
    "Colorer selon", options=color_options,
    format_func=lambda k: "Aucune" if k == "Aucune" else ("Équipe" if k == "team" else metric_label(k)),
    index=color_options.index(default_color),
)

size_options = ["Aucune"] + metric_keys
default_size = "minutes_per_game" if "minutes_per_game" in metric_keys else "Aucune"
size_key = st.sidebar.selectbox(
    "Taille des points selon", options=size_options,
    format_func=lambda k: "Aucune" if k == "Aucune" else metric_label(k),
    index=size_options.index(default_size),
)

st.sidebar.markdown("---")
st.sidebar.subheader("Filtres")
min_minutes = st.sidebar.slider(
    "Minutes par match minimum (filtrer le bruit \"garbage time\")",
    min_value=0.0, max_value=40.0, value=8.0, step=1.0,
)
min_games = st.sidebar.slider(
    "Nombre de matchs joués minimum",
    min_value=0, max_value=82, value=0, step=1,
    help=(
        "Filtre uniquement l'affichage (graph + tableau). Le modèle de salaire attendu a son "
        "propre seuil interne (15 matchs, voir data_sources/nba.MIN_GAMES_FOR_FIT), indépendant "
        "de ce curseur — les joueurs sous ce seuil sont visibles par défaut (badge ⚠️ losange "
        "creux dans le graph), à toi de décider si tu veux les masquer."
    ),
)

st.sidebar.markdown("---")
n_estimated = int(df.get("salary_is_estimated", pd.Series(dtype=bool)).sum())
include_estimated_salary = True
if n_estimated:
    include_estimated_salary = st.sidebar.checkbox(
        f"Inclure les salaires estimés (année proche) — {n_estimated} joueur(s)",
        value=True,
        help=(
            "Le dataset Kaggle n'a pas de ligne salaire pour l'année exacte de tous les "
            "joueurs. Pour ceux-là, on utilise le salaire de l'année la plus proche "
            "disponible (± 2 ans). Décoche pour ne garder que les salaires exacts."
        ),
    )

st.sidebar.markdown("---")
st.sidebar.button("🔄 Rafraîchir les données (re-télécharger)", on_click=_handle_refresh_click)


# --------------------------------------------------------------------------
# Filtrage
# --------------------------------------------------------------------------
plot_df = df.copy()
if "minutes_per_game" in plot_df.columns:
    plot_df = plot_df[plot_df["minutes_per_game"].fillna(0) >= min_minutes]
if "games_played" in plot_df.columns:
    plot_df = plot_df[plot_df["games_played"].fillna(0) >= min_games]
if team_filter:
    plot_df = plot_df[plot_df["team"].isin(team_filter)]
if not include_estimated_salary and "salary_is_estimated" in plot_df.columns:
    estimated_mask = plot_df["salary_is_estimated"].fillna(False)
    salary_cols = [
        c for c in (
            "salary", "salary_musd", "salary_pct_cap",
            "value_added", "value_added_musd", "value_added_pct_cap",
        )
        if c in plot_df.columns
    ]
    plot_df.loc[estimated_mask, salary_cols] = pd.NA
plot_df = plot_df.dropna(subset=[x_key, y_key])

# Le classement d'équipes bascule $ / % du plafond selon le mode, comme la couleur par défaut
# du scatter plot ci-dessus : le $ brut n'est pas comparable entre saisons très éloignées en
# mode "Toutes les saisons" (plafond x6 entre 1996-97 et 2025-26), donc % du plafond dans ce
# cas ; en mode saison unique, le $ reste plus parlant.
ranking_value_col = "value_added_pct_cap" if is_all_seasons else "value_added_musd"

# DataFrame dédié au classement d'équipes (section tout en bas de page) : mêmes filtres
# "minutes/matchs minimum" et "salaires estimés" que plot_df, mais SANS le filtre équipe (sinon
# le classement n'aurait plus de sens) ni le dropna sur x_key/y_key (le classement porte sur
# ranking_value_col, indépendamment des métriques choisies pour le scatter plot).
# Construit à partir de team_ranking_source_df (TOUJOURS saison régulière, voir plus haut où il
# est défini) et NON `df` — `df` reflète le sélecteur "Statistiques utilisées" (saison unique) et
# peut donc être en playoffs, ce que ce classement ne doit jamais suivre.
team_ranking_df = team_ranking_source_df.copy()
if "minutes_per_game" in team_ranking_df.columns:
    team_ranking_df = team_ranking_df[team_ranking_df["minutes_per_game"].fillna(0) >= min_minutes]
if "games_played" in team_ranking_df.columns:
    team_ranking_df = team_ranking_df[team_ranking_df["games_played"].fillna(0) >= min_games]
if not include_estimated_salary and "salary_is_estimated" in team_ranking_df.columns:
    team_ranking_df = team_ranking_df[~team_ranking_df["salary_is_estimated"].fillna(False)]
team_ranking_df = team_ranking_df.dropna(subset=[ranking_value_col, "team"])

x_meta, y_meta = metrics[x_key], metrics[y_key]


# --------------------------------------------------------------------------
# Contenu principal
# --------------------------------------------------------------------------
st.title(f"🏀 {sport.label} — {season}")

# Texte de méthodologie/sources — calculé ici (dépend de x_key/y_key/color_key) mais affiché
# plus bas dans un expander replié, pour que le graph suive le titre sans texte interposé.
data_sources_caption = (
    "Stats de jeu : `nba_api` (stats.nba.com, live)  ·  Salaire & PER : dataset Kaggle "
    "ratin21/nba-player-stats-and-salaries-2010-2025 pour 2010-11 et après, complété par le "
    "dataset CC0 iampunitkmryh/nba-players-details-198518 pour 1996-97→2009-10 "
    "(les deux sourcés de Basketball-Reference / HoopsHype — voir `data_sources/nba.py` pour la "
    "frontière exacte)  ·  Salaire/salaire attendu/valeur ajoutée aussi disponibles normalisés "
    "en % du plafond salarial officiel de la saison (`data_sources/nba.NBA_SALARY_CAP_BY_SEASON`), "
    "pour rester comparables entre saisons malgré la forte hausse du plafond dans le temps  ·  "
    "Données mises en cache localement dans `data_cache/`."
)
value_added_caption = None
# Détail par saison du modèle (mode "Toutes les saisons" uniquement) : affiché sous forme de
# tableau dans l'expander méthodologie plutôt que dans la caption elle-même — avec ~30 saisons
# désormais (contre 3 initialement), une seule ligne de texte listant chaque saison serait
# illisible.
value_added_per_season_df = None
# Limite testée et documentée (voir README, section "Biais de sous-valorisation des scoreurs
# purs") : 3 pistes de correction testées et rejetées (PIE seul, PIE + variable non corrélée au
# poste, impact_hors_scoring à poids réduit) — le biais survit aux trois, donc probablement une
# caractéristique réelle du marché salarial plutôt qu'un artefact du modèle. Pas une anomalie de
# calcul à corriger silencieusement : signalée explicitement à l'utilisateur ici.
SCORER_BIAS_CAVEAT = (
    " ⚠️ Limite connue et testée du modèle : les purs scoreurs à très haut volume (peu de "
    "rebonds/contres/passes/interceptions relativement à leur profil) peuvent apparaître plus "
    "\"surpayés\" (valeur ajoutée très négative) que leur valeur réelle ne le justifierait — 3 "
    "pistes de correction ont été testées et rejetées (voir README), le biais persiste même sans "
    "`impact_hors_scoring` dans le modèle. Pas une anomalie de calcul."
)

# Diagnostic (revérifié sur 6 saisons, 1998-99 à 2025-26) : impact_hors_scoring BRUT favorise
# structurellement les intérieurs (poids des rebonds ~54% du composite en moyenne, écart brut
# Intérieur-Ailier passé de +0.6 pt en 1998-99 à +2 à +2.8 pts sur 2023-24/2025-26) — déjà corrigé
# dans le modèle par le z-score de poste (impact_hors_scoring_zscore_poste, voir historique de
# VALUE_ADDED_PERFORMANCE_COLS dans data_sources/nba.py), qui n'utilise QUE cette colonne, jamais
# la brute. Un résidu plus faible subsiste néanmoins certaines saisons (3 sur 6 testées,
# p<0.05) mais SANS sens constant (Intérieur sous-évalué en 1998-99, surévalué en 2005-06 et
# 2023-24) — contrairement au biais brut d'origine (toujours dans le même sens, toujours très
# significatif), ce qui pointe vers du bruit saisonnier plutôt qu'un défaut structurel de la
# formule. Décision : caveat documenté, pas de nouvel ajustement du modèle (même logique que
# SCORER_BIAS_CAVEAT).
POSITION_BIAS_CAVEAT = (
    " ⚠️ Le modèle normalise déjà `impact_hors_scoring` par un z-score calculé À L'INTÉRIEUR de "
    "chaque groupe de poste, pour corriger un biais mesuré sur la colonne brute (les intérieurs "
    "dominent structurellement sur les rebonds, un écart qui s'est creusé avec le temps). Un "
    "résidu plus faible subsiste certaines saisons, mais sans sens constant (intérieurs tantôt "
    "sous-évalués, tantôt sur-évalués selon la saison) — plutôt du bruit saisonnier qu'un défaut "
    "structurel de la formule."
)

# Mention méthodologique du delta de rythme de jeu saison régulière / playoffs (voir le
# diagnostic de faisabilité playoffs) — mesuré, pas théorique : pace ligue quasi neutre dans les
# années 90-2000 (ex. -0.7 en 1996-97), jusqu'à -5.5 possessions/48min en 2023-24. Un volume par
# match plus faible en playoffs (moins de possessions) ne signifie donc pas nécessairement une
# baisse de niveau individuel — s'ajoute une défense plus dure/préparée et des rotations
# resserrées. Visible uniquement quand une des 2 options playoffs est sélectionnée (voir
# stats_period plus haut), même style que SCORER_BIAS_CAVEAT.
PLAYOFF_PACE_CAVEAT = (
    " ⚠️ Écart de rythme de jeu saison régulière / playoffs : les playoffs se jouent à un rythme "
    "plus lent (jusqu'à -5.5 possessions/48min en 2023-24, écart quasi neutre dans les années "
    "90-2000 mais nettement plus marqué depuis) — un volume de stats par match plus faible en "
    "playoffs ne traduit donc pas forcément une baisse de niveau individuel, la défense plus "
    "dure et les rotations resserrées jouent aussi. Pas corrigé dans le calcul, à garder en tête "
    "en comparant les deux périodes."
)

missing_salary = df["salary"].isna().all() if "salary" in df.columns else True
if missing_salary and "salary_musd" in (x_key, y_key, color_key):
    st.warning(
        "⚠️ Aucun salaire trouvé pour cette saison. Le dataset Kaggle n'est peut-être pas "
        "encore configuré (voir `README.md` — téléchargement manuel possible) ou ne couvre "
        "pas encore cette saison."
    )

value_added_keys = {
    "expected_salary_musd", "value_added_musd",
    "expected_salary_pct_cap", "value_added_pct_cap",
}
if "value_added_r2" in df.columns:
    if is_all_seasons:
        # Un modèle DIFFÉRENT est ajusté séparément par saison (voir data_sources/nba.py) — pas
        # un modèle unique sur toutes les saisons combinées. R²/marge sont donc affichés par
        # saison, jamais un seul chiffre global qui serait trompeur (mélangerait des dizaines
        # de modèles distincts, ajustés sur des marchés salariaux très différents dans le temps).
        per_season = df.drop_duplicates(subset="season").sort_values("season")
        failed_models = per_season[per_season["value_added_r2"].isna()]
        ok_models = per_season[per_season["value_added_r2"].notna()]
        if len(failed_models):
            st.warning(
                "⚠️ Le modèle de salaire attendu n'a pas pu être ajusté pour : "
                + ", ".join(failed_models["season"])
                + " (données de postes ou autre indisponibles). Salaire attendu / Valeur ajoutée "
                "sont indisponibles pour ces saisons-là."
            )
        if len(ok_models) and value_added_keys & {x_key, y_key, color_key}:
            r2_min, r2_max = ok_models["value_added_r2"].min(), ok_models["value_added_r2"].max()
            value_added_caption = (
                "📐 Salaire attendu = régression linéaire ajustée SÉPARÉMENT pour chaque saison "
                f"(un modèle par saison, pas un modèle unique sur toutes les saisons combinées) — "
                f"{len(ok_models)} saison(s) avec un modèle valide, R² entre {r2_min:.2f} et "
                f"{r2_max:.2f} (détail saison par saison ci-dessous). Modèle simple à but "
                "exploratoire, pas une évaluation contractuelle réelle."
                + SCORER_BIAS_CAVEAT + POSITION_BIAS_CAVEAT
            )
            value_added_per_season_df = ok_models[
                ["season", "value_added_r2", "value_added_n_fit", "value_added_residual_std_musd",
                 "value_added_residual_median_musd", "value_added_residual_q1_musd", "value_added_residual_q3_musd"]
            ].rename(columns={
                "season": "Saison", "value_added_r2": "R²",
                "value_added_n_fit": "Taille échantillon", "value_added_residual_std_musd": "Marge (± M$)",
                "value_added_residual_median_musd": "Médiane (M$)",
                "value_added_residual_q1_musd": "Q1 (M$)", "value_added_residual_q3_musd": "Q3 (M$)",
            }).reset_index(drop=True)
    else:
        r2 = df["value_added_r2"].iloc[0]
        n_fit = int(df["value_added_n_fit"].iloc[0]) if "value_added_n_fit" in df.columns else 0
        if pd.notna(r2):
            # Cette légende n'est affichée (dans l'expander plus bas) que si l'utilisateur
            # regarde effectivement une métrique liée — pas la peine de la pousser sinon.
            if value_added_keys & {x_key, y_key, color_key}:
                residual_std = df["value_added_residual_std_musd"].iloc[0] if "value_added_residual_std_musd" in df.columns else None
                # Montant entouré de backticks (`± X M$`) : un `$` isolé (hors backticks) est
                # interprété par le rendu Markdown de Streamlit comme un délimiteur de LaTeX
                # inline -- un nombre IMPAIR de `$` dans le texte final casse le rendu (italique +
                # espaces avalés) à partir du `$` non apparié. Repéré ici après un audit complet
                # (pas juste les 2 termes déjà corrigés une fois) : `M$` apparaît 3 fois entre
                # margin_txt et distribution_txt, jamais protégé.
                margin_txt = (
                    f" Le salaire attendu affiché dans l'infobulle inclut une marge d'incertitude "
                    f"(`± {residual_std:.1f} M$`, l'écart-type des résidus du modèle sur ce même "
                    "échantillon) — en-dessous de cette marge, une valeur ajoutée est signalée comme "
                    "potentiellement du bruit statistique plutôt qu'un vrai écart perf/salaire."
                    if residual_std is not None and pd.notna(residual_std) else ""
                )
                # Médiane + IQR (Q1-Q3) des résidus de l'échantillon de fit, en complément de
                # l'écart-type ci-dessus : celui-ci ne dit rien de la SYMÉTRIE de la distribution
                # (ex. médiane éloignée de 0 = résidus décalés d'un côté, pas juste dispersés).
                residual_median = df["value_added_residual_median_musd"].iloc[0] if "value_added_residual_median_musd" in df.columns else None
                residual_q1 = df["value_added_residual_q1_musd"].iloc[0] if "value_added_residual_q1_musd" in df.columns else None
                residual_q3 = df["value_added_residual_q3_musd"].iloc[0] if "value_added_residual_q3_musd" in df.columns else None
                distribution_txt = (
                    f" Médiane des résidus : `{residual_median:+.1f} M$` (IQR "
                    f"`[{residual_q1:+.1f}, {residual_q3:+.1f}] M$`, 50% des résidus dans cet intervalle)."
                    if all(v is not None and pd.notna(v) for v in (residual_median, residual_q1, residual_q3))
                    else ""
                )
                value_added_caption = (
                    f"📐 Salaire attendu = régression linéaire (salaire ~ stats de performance) "
                    f"ajustée sur un sous-ensemble de {n_fit} joueurs (R² = {r2:.2f}), puis appliquée "
                    "à tout le monde, y compris ceux exclus de l'ajustement (voir `data_sources/<sport>.py` "
                    "pour le critère de sélection). Modèle simple à but exploratoire, pas une évaluation "
                    "contractuelle réelle." + margin_txt + distribution_txt
                    + SCORER_BIAS_CAVEAT + POSITION_BIAS_CAVEAT
                    + (PLAYOFF_PACE_CAVEAT if stats_period != "regular" else "")
                )
        else:
            # Inconditionnel (contrairement à la légende ci-dessus) : un modèle non ajusté est un
            # vrai problème de données pour cette saison, à signaler même si l'utilisateur ne
            # regarde pas Salaire attendu/Valeur ajoutée en ce moment — pas de silence total.
            st.warning(
                "⚠️ Le modèle de salaire attendu n'a pas pu être ajusté pour cette saison (données "
                "de postes ou autre indisponibles, probablement un souci réseau passager malgré les "
                "tentatives automatiques). Salaire attendu / Valeur ajoutée sont indisponibles pour "
                "l'instant — recharge la page pour réessayer."
            )

if plot_df.empty:
    st.warning("Aucun joueur ne correspond aux filtres actuels (essaie de baisser le minimum de minutes).")
    st.stop()

# Badge visuel (pas d'exclusion) pour les échantillons de saison trop courts — voir
# nba.MIN_GAMES_FOR_FIT. On garde low_sample_size (bool) pour la logique et on dérive un
# libellé lisible pour la légende du symbole plutôt que d'afficher "True"/"False".
symbol_key = None
if "low_sample_size" in plot_df.columns:
    plot_df["Échantillon"] = plot_df["low_sample_size"].map(
        {True: "⚠️ Échantillon court (peu de matchs)", False: "Échantillon normal"}
    )
    symbol_key = "Échantillon"


def _format_value(value, fmt: str) -> str | None:
    if pd.isna(value):
        return None
    try:
        return format(value, fmt)
    except (ValueError, TypeError):
        return str(value)


def _build_hover_text(row) -> str:
    """Infobulle 100% en français, libellés naturels, uniquement l'essentiel pour
    interpréter le point : équipe, salaire réel/attendu/valeur ajoutée (toujours,
    peu importe les axes choisis), puis les métriques utilisées en X/Y/couleur/taille
    (sans doublon avec ce qui précède). L'alerte petit échantillon n'apparaît que pour
    les joueurs concernés — rien n'est affiché pour les autres."""
    lines = []
    if pd.notna(row.get("team")):
        lines.append(f"Équipe : {row['team']}")
    # Utile seulement en mode "Toutes les saisons" (sinon déjà indiqué dans le titre) : un même
    # joueur y apparaît comme plusieurs points distincts, un par saison jouée.
    if is_all_seasons and pd.notna(row.get("season")):
        lines.append(f"Saison : {row['season']}")

    salary_str = _format_value(row.get("salary_musd"), ",.2f")
    if salary_str is not None:
        suffix = " (estimé, année proche)" if row.get("salary_is_estimated") else ""
        lines.append(f"Salaire réel : {salary_str} M$" + suffix)

    margin = row.get("value_added_residual_std_musd")
    expected_str = _format_value(row.get("expected_salary_musd"), ",.2f")
    if expected_str is not None:
        margin_str = f" (± {margin:,.1f} M$)" if pd.notna(margin) else ""
        lines.append(f"Salaire attendu : {expected_str} M$" + margin_str)

    value_added = row.get("value_added_musd")
    if pd.notna(value_added):
        sign = "+" if value_added >= 0 else ""
        lines.append(f"Valeur ajoutée : {sign}{value_added:,.2f} M$")
        # Signal plutôt que forme/couleur supplémentaire sur le graph (le losange sert déjà à
        # l'alerte échantillon court) : si |value_added| < marge d'incertitude du modèle, ça
        # pourrait n'être que du bruit statistique plutôt qu'un vrai écart perf/salaire.
        if pd.notna(margin) and abs(value_added) < margin:
            lines.append(
                "⚠️ Valeur ajoutée dans la marge d'incertitude du modèle, à interpréter avec prudence."
            )

    # Récompenses individuelles (voir _awards, calculée via sport.award_badges_fn plus bas) —
    # toujours dans le tooltip quel que soit le mode (saison unique ou "Toutes les saisons"),
    # contrairement au badge visuel sur le graph lui-même qui est simplifié en mode dense (voir
    # la trace "award_text_rows" plus bas).
    awards = row.get("_awards")
    if awards:
        lines.append(
            "🏅 Récompenses : " + ", ".join(
                f"{AWARD_ICONS.get(a, '')} {AWARD_LABELS.get(a, a)}" for a in awards
            )
        )

    shown_keys = {"salary_musd", "expected_salary_musd", "value_added_musd"}
    for key in (x_key, y_key, color_key, size_key):
        if key in metrics and key not in shown_keys:
            val_str = _format_value(row.get(key), metrics[key].fmt)
            if val_str is not None:
                lines.append(f"{metrics[key].label} : {val_str}")
            shown_keys.add(key)

    games = row.get("games_played")
    if row.get("low_sample_size"):
        games_str = f"{games:.0f}" if pd.notna(games) else "?"
        minutes = row.get("minutes_per_game")
        minutes_str = f", {minutes:.1f} min/match" if pd.notna(minutes) else ""
        lines.append(f"⚠️ Échantillon court : {games_str} matchs joués{minutes_str}")
    elif pd.notna(games):
        lines.append(f"Matchs joués : {games:.0f}")

    return "<br>".join(lines)


# _awards déjà présente (calculée sur df entier avant filtrage, voir plus haut) : propagée telle
# quelle depuis df via plot_df = df.copy() + les filtres, pas recalculée ici.
plot_df["_hover"] = plot_df.apply(_build_hover_text, axis=1)

# Bordure dorée COLLÉE au marqueur du joueur primé (même taille que son propre point), pas un
# anneau séparé plus grand : ajustable uniquement via marker.line.color/width du point lui-même,
# donc calculée ici en tant que colonnes (une par point) et transportée via custom_data jusqu'à
# fig.for_each_trace plus bas (px.scatter n'a pas de paramètre pour mapper une colonne sur
# marker.line.color directement).
# En mode "Toutes les saisons" : un or vif semi-transparent (1res versions testées) devenait
# presque invisible contre un remplissage jaune-vert -- justement la teinte la plus fréquente au
# milieu de l'échelle RdYlGn, vérifié par comparaison directe (image de contrôle) sur 3
# remplissages (jaune pâle/jaune-vert/vert) : illisible en semi-transparent, nettement visible en
# "darkgoldenrod" plein. D'où une teinte plus sombre plutôt qu'une transparence réduite — une
# opacité plus faible aurait le même problème de fond quel que soit le niveau choisi.
_award_border_color = "#B8860B" if is_all_seasons else "#FFD700"  # darkgoldenrod vs or vif
_award_border_width = 2.2 if is_all_seasons else 2.5
plot_df["_border_color"] = plot_df["_awards"].map(lambda a: _award_border_color if a else "DarkSlateGrey")
plot_df["_border_width"] = plot_df["_awards"].map(lambda a: _award_border_width if a else 0.5)

fig = px.scatter(
    plot_df,
    x=x_key,
    y=y_key,
    color=None if color_key == "Aucune" else color_key,
    size=None if size_key == "Aucune" else size_key,
    symbol=symbol_key,
    symbol_map={"Échantillon normal": "circle", "⚠️ Échantillon court (peu de matchs)": "diamond"} if symbol_key else None,
    size_max=28,
    hover_name="player",
    custom_data=["_hover", "_border_color", "_border_width"],
    color_continuous_scale="RdYlGn" if color_key in metrics and metrics[color_key].category in ("Valeur", "Efficacité") else "Viridis",
    labels={x_key: x_meta.label, y_key: y_meta.label, **({color_key: metrics[color_key].label} if color_key in metrics else {})},
    template="plotly_white",
    height=700,
    # PAS de render_mode forcé : plotly express bascule automatiquement en WebGL (Scattergl) au-delà
    # de ~1000 points (cas courant du mode "Toutes les saisons", plusieurs milliers de lignes) --
    # accélération GPU précieuse à cette échelle (pan/zoom/hover nettement plus fluides). Forcer le
    # SVG globalement pour régler le z-order du surlignage (essayé, puis retiré) dégradait au
    # contraire la fluidité du nuage principal en mode "Toutes les saisons". Le vrai fix, plus bas :
    # faire correspondre le moteur de la trace de surlignage à celui réellement choisi ici pour le
    # nuage (Scattergl si bascule WebGL, Scatter sinon), plutôt que d'imposer le même moteur partout.
)
fig.update_traces(
    hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]}<extra></extra>",
)


def _apply_award_borders(trace) -> None:
    # symbol=symbol_key scinde le nuage principal en plusieurs traces (une par catégorie
    # d'échantillon) -- chacune ne contient qu'un SOUS-ENSEMBLE de plot_df, dans un ordre propre à
    # px.scatter. custom_data[1]/[2] (couleur/largeur de bordure) voyage avec chaque ligne à
    # travers ce découpage, donc les relire ici depuis trace.customdata donne le bon tableau pour
    # CETTE trace précise, sans avoir à reconstituer le découpage nous-mêmes.
    if trace.customdata is None or len(trace.customdata) == 0:
        return
    trace.marker.line.color = [c[1] for c in trace.customdata]
    trace.marker.line.width = [float(c[2]) for c in trace.customdata]


fig.for_each_trace(_apply_award_borders)
fig.update_layout(
    xaxis_title=x_meta.label,
    yaxis_title=y_meta.label,
    # La légende des symboles (Échantillon) et la barre de couleur (colorbar) se
    # disputaient toutes les deux le coin haut-droit par défaut et se chevauchaient. On les
    # sépare explicitement : légende horizontale au-dessus du graph, colorbar recentrée et
    # raccourcie sur la droite — indépendant de la métrique choisie en couleur.
    legend=dict(
        title_text="",
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0,
    ),
    coloraxis_colorbar=dict(
        len=0.85,
        yanchor="middle",
        y=0.45,
    ),
    margin=dict(t=90),
)

# Surlignage du joueur recherché : trace séparée ajoutée PAR-DESSUS le nuage existant (dernière
# trace = dessinée au-dessus dans Plotly — vrai pour deux traces de même moteur de rendu). Le
# nuage principal ci-dessus peut être en Scatter (SVG) ou Scattergl (WebGL) selon sa taille (voir
# commentaire plus haut) ; WebGL et SVG sont composités dans des calques séparés par le
# navigateur, donc l'ordre des traces ne suffit à garantir le z-order QUE si le surlignage utilise
# le MÊME moteur que le nuage — d'où la détection ci-dessous plutôt qu'un go.Scatter fixe. Ne
# modifie aucun point du graph, juste un contour + nom ajoutés visuellement. hoverinfo="skip" pour
# ne pas dupliquer/bloquer l'infobulle du point réel. Taille (34) volontairement au-dessus de
# size_max=28 du nuage principal (jamais recouvert par un marqueur du nuage, même le plus gros) ;
# contour épais (6px) et couleur qui tranche sur les deux échelles de couleur utilisées (RdYlGn /
# Viridis) pour rester lisible même sans chevauchement.
highlight_scatter_cls = go.Scattergl if type(fig.data[0]).__name__ == "Scattergl" else go.Scatter

# Badges de récompenses individuelles (MVP, DPOY, ROY, MIP, 6MOY, MVP des Finales) : la bordure
# dorée du point lui-même (voir _award_border_color/_border_width + fig.for_each_trace plus haut)
# marque déjà le lauréat sans trace séparée. Reste ici uniquement l'émoji composite au-dessus du
# point (ex. "👑🎖️" si cumul MVP + MVP des Finales la même saison), qui complète la bordure — la
# couleur seule ne dit pas QUELLE récompense. Affiché SEULEMENT en saison unique : en mode "Toutes
# les saisons" (~180 points primés sur toute la période, souvent proches les uns des autres dans
# l'espace salaire/perf), des étiquettes texte permanentes se chevaucheraient — voir proposition
# validée ; le détail complet reste de toute façon dans le tooltip (_build_hover_text) dans les
# deux modes. Ajouté AVANT le surlignage du joueur recherché ci-dessous (donc dessous, cohérent
# avec le z-order).
award_rows = plot_df[plot_df["_awards"].map(bool)]
if not award_rows.empty and AWARD_ICONS and not is_all_seasons:
    # Le joueur recherché a déjà son propre label texte "top center" (surlignage ci-dessous) —
    # exclu ici pour ne pas superposer deux textes au même endroit ; sa (ses) éventuelle(s)
    # récompense(s) reste(nt) visible(s) via la bordure dorée de son point + le tooltip.
    text_rows = award_rows if searched_player == "Aucun" else award_rows[award_rows["player"] != searched_player]
    if not text_rows.empty:
        badge_labels = text_rows["_awards"].map(
            lambda codes: "".join(AWARD_ICONS.get(c, "") for c in codes)
        )
        fig.add_trace(
            highlight_scatter_cls(
                x=text_rows[x_key],
                y=text_rows[y_key],
                mode="text",
                text=badge_labels,
                textposition="top center",
                textfont=dict(size=16),
                hoverinfo="skip",
                showlegend=False,
            )
        )

if searched_player != "Aucun":
    highlight_row = plot_df[plot_df["player"] == searched_player]
    if highlight_row.empty:
        st.info(
            f"🔍 **{searched_player}** ne correspond à aucun point affiché avec les filtres "
            "actuels (minutes/matchs joués minimum, équipe...). Élargis les filtres pour le voir."
        )
    else:
        # En mode "Toutes les saisons", un même joueur peut avoir plusieurs points (un par
        # saison) — chacun est entouré, avec la saison ajoutée au label pour les distinguer.
        highlight_labels = (
            [f"{searched_player} ({s})" for s in highlight_row["season"]]
            if is_all_seasons
            else [searched_player] * len(highlight_row)
        )
        fig.add_trace(
            highlight_scatter_cls(
                x=highlight_row[x_key],
                y=highlight_row[y_key],
                mode="markers+text",
                marker=dict(size=34, color="rgba(0,0,0,0)", line=dict(color="#FF1E56", width=6)),
                text=highlight_labels,
                textposition="top center",
                textfont=dict(size=13, color="#FF1E56", family="Arial Black"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

st.plotly_chart(fig, width='stretch')

st.caption(
    "💡 Repère les joueurs **sous-évalués** (haut à gauche : forte perf, faible salaire) "
    "vs **surévalués** (bas à droite : faible perf, gros salaire) en mettant le salaire en X "
    "et une métrique de performance en Y."
)
if symbol_key:
    st.caption(
        "◆ Losange = échantillon de saison court (peu de matchs joués) — affiché (même "
        "remplissage coloré que les ronds) mais "
        "exclu de l'ajustement du modèle de salaire attendu, sa moyenne par match peut être "
        "moins représentative d'une saison complète."
    )

with st.expander("ℹ️ Sources des données et méthodologie du modèle", expanded=False):
    st.caption(data_sources_caption)
    if value_added_caption:
        st.caption(value_added_caption)
    if value_added_per_season_df is not None:
        st.dataframe(
            value_added_per_season_df.style.format({
                "R²": "{:.2f}", "Marge (± M$)": "{:.1f}",
                "Médiane (M$)": "{:+.1f}", "Q1 (M$)": "{:+.1f}", "Q3 (M$)": "{:+.1f}",
            }),
            # use_container_width (pas width='stretch') : repéré en local que st.dataframe (à la
            # différence de st.plotly_chart) crashe sur width='stretch' avec un streamlit trop
            # ancien (TypeError 'stretch' has type str, but expected int) -- ici précisément parce
            # que le mauvais interpréteur tournait (anaconda 1.32.0 au lieu du .venv du projet,
            # confirmé). use_container_width reste universellement supporté, sans dépendre de
            # l'environnement effectivement utilisé pour lancer l'app.
            use_container_width=True, height=min(400, 38 * (len(value_added_per_season_df) + 1)),
        )

with st.expander("📋 Voir les données détaillées"):
    display_cols = ["player", "team"] + sorted(set([x_key, y_key] + ([color_key] if color_key in metrics else [])))
    if symbol_key:
        display_cols += [c for c in ("games_played", symbol_key) if c not in display_cols]
    st.dataframe(
        plot_df[display_cols].sort_values(y_key, ascending=False).reset_index(drop=True),
        use_container_width=True,  # voir commentaire ci-dessus (expander méthodologie)
    )

# --------------------------------------------------------------------------
# Trajectoire de valeur ajoutée par joueur (toutes saisons, joueur recherché uniquement --
# indépendant de la saison affichée à l'écran, voir load_all_seasons_data).
# --------------------------------------------------------------------------
if searched_player != "Aucun":
    # Piloté par st.session_state (key=) plutôt que juste "if searched_player != Aucun" : ce
    # 2e critère à lui seul ne suffisait pas, il laissait tout le contenu lourd (DataFrame de
    # trajectoire, segmentation, go.Figure() à N traces) se reconstruire à CHAQUE rerun tant
    # qu'un joueur restait sélectionné, même expander replié et même quand seul un widget sans
    # rapport (slider, filtre équipe...) changeait — repéré comme un des facteurs de la
    # régression de fluidité générale. on_change="rerun" (Streamlit >= 1.34 : les expanders sont
    # sinon purement client-side et ne déclenchent aucun rerun à l'ouverture) garantit qu'ouvrir
    # le panneau déclenche bien un rerun immédiat pour peupler le contenu, plutôt que de rester
    # vide jusqu'au prochain changement de widget sans rapport.
    TRAJ_EXPANDER_KEY = "traj_expander_open"
    with st.expander(
        f"📈 Trajectoire de valeur ajoutée — {searched_player}",
        key=TRAJ_EXPANDER_KEY, on_change="rerun",
    ):
        if not st.session_state.get(TRAJ_EXPANDER_KEY, False):
            # Rien de plus n'est calculé tant que le panneau n'est pas réellement ouvert -- ni le
            # chargement de l'historique complet, ni la construction de la figure.
            st.caption("Ouvre ce panneau pour calculer et afficher la trajectoire.")
        else:
            if is_all_seasons:
                traj_source_df, traj_failed = df, failed_seasons
            else:
                traj_source_df, traj_failed = load_all_seasons_data(sport.key, tuple(ALL_SEASONS_KEYS), force_refresh)

            if traj_failed:
                st.caption(
                    "⚠️ Historique incomplet : " + ", ".join(s for s, _ in traj_failed)
                    + " n'ont pas pu être chargées, absentes de la trajectoire."
                )

            traj_cols = {
                "player", "season", "value_added_pct_cap", "value_added_residual_std_pct_cap",
                "low_sample_size", "games_played", "minutes_per_game",
            }
            if not traj_cols <= set(traj_source_df.columns):
                st.info("Trajectoire indisponible pour ce sport (colonnes requises absentes).")
            else:
                # Ordre chronologique : les saisons "YYYY-YY" se trient correctement en simple tri de
                # chaînes (même longueur, année en préfixe) — pas besoin de parser l'année.
                full_seasons_asc = sorted(ALL_SEASONS_KEYS)
                player_rows = traj_source_df[traj_source_df["player"] == searched_player]
                traj = pd.DataFrame({"season": full_seasons_asc}).merge(
                    player_rows[list(traj_cols - {"player"})], on="season", how="left",
                )
                traj["present"] = traj["value_added_pct_cap"].notna()

                if not traj["present"].any():
                    st.info(f"Aucune donnée de valeur ajoutée disponible pour {searched_player} sur la période couverte.")
                else:
                    # Segmente en tronçons de saisons CONSÉCUTIVES présentes : une vraie interruption de
                    # carrière (saison(s) hors NBA dans la période couverte -- PAS juste une saison
                    # exclue du fit pour low_sample_size, qui n'empêche pas value_added d'être calculé
                    # et affiché) tombe entre deux tronçons distincts. Une trace Plotly séparée par
                    # tronçon garantit qu'AUCUNE ligne ne relie les deux côtés d'un trou de carrière —
                    # pas d'interpolation silencieuse, contrairement à ce qu'on obtiendrait en comptant
                    # sur le simple "connectgaps=False" de Plotly sur une unique trace avec des NaN.
                    # Vérifié sur un cas réel dans les 30 saisons couvertes : Michael Jordan, présent en
                    # 1996-97/1997-98, absent 1998-99 à 2000-01 (retraite), réapparaît 2001-02/2002-03.
                    traj["seg_id"] = (~traj["present"]).cumsum()
                    segments = [g for _, g in traj[traj["present"]].groupby("seg_id")]

                    n_gaps = len(segments) - 1
                    if n_gaps > 0:
                        st.caption(
                            f"ℹ️ {n_gaps} interruption(s) détectée(s) sur la période couverte (saison(s) "
                            "hors NBA ou données indisponibles) — la ligne est coupée à cet endroit, "
                            "aucune interpolation entre les deux côtés."
                        )

                    fig_traj = go.Figure()
                    for seg in segments:
                        hover_texts = []
                        for _, r in seg.iterrows():
                            line = f"Valeur ajoutée : {r['value_added_pct_cap']:+.1%}"
                            margin = r["value_added_residual_std_pct_cap"]
                            if pd.notna(margin):
                                line += f" (± {margin:.1%})"
                            parts = [f"Saison : {r['season']}", line]
                            if r.get("low_sample_size"):
                                games_txt = f"{r['games_played']:.0f}" if pd.notna(r["games_played"]) else "?"
                                minutes_val = r.get("minutes_per_game")
                                minutes_txt = f", {minutes_val:.1f} min/match" if pd.notna(minutes_val) else ""
                                parts.append(f"⚠️ Échantillon court : {games_txt} matchs joués{minutes_txt}")
                            hover_texts.append("<br>".join(parts))

                        margin_filled = seg["value_added_residual_std_pct_cap"].fillna(0)
                        upper = (seg["value_added_pct_cap"] + margin_filled).tolist()
                        lower = (seg["value_added_pct_cap"] - margin_filled).tolist()
                        seasons_list = seg["season"].tolist()
                        fig_traj.add_trace(go.Scatter(
                            x=seasons_list + seasons_list[::-1],
                            y=upper + lower[::-1],
                            fill="toself", fillcolor="rgba(31,119,180,0.15)",
                            line=dict(width=0), hoverinfo="skip", showlegend=False,
                        ))
                        symbols = seg["low_sample_size"].fillna(False).map({True: "diamond", False: "circle"}).tolist()
                        fig_traj.add_trace(go.Scatter(
                            x=seasons_list, y=seg["value_added_pct_cap"].tolist(),
                            mode="lines+markers",
                            line=dict(color="#1f77b4", width=2),
                            marker=dict(size=9, symbol=symbols, color="#1f77b4", line=dict(width=1, color="white")),
                            customdata=hover_texts,
                            hovertemplate="%{customdata}<extra></extra>",
                            showlegend=False,
                        ))

                    fig_traj.add_hline(y=0, line=dict(color="gray", width=1, dash="dot"))
                    fig_traj.update_layout(
                        template="plotly_white", height=420,
                        xaxis=dict(title="", categoryorder="array", categoryarray=full_seasons_asc),
                        yaxis=dict(title="Valeur ajoutée (% du plafond)", tickformat=".0%"),
                        margin=dict(t=20, b=10, l=10, r=10),
                    )
                    st.plotly_chart(fig_traj, width='stretch')
                    st.caption(
                        "Bande ombrée = marge d'incertitude du modèle (± écart-type des résidus), "
                        "largeur propre à chaque saison — le R² du modèle varie de 0.32 à 0.60 selon "
                        "les saisons (voir README, section \"Stabilité du R²\"), donc la fiabilité de la "
                        "trajectoire n'est pas uniforme dans le temps. ◆ Losange = saison exclue de "
                        "l'ajustement du modèle pour échantillon trop court (`low_sample_size`), "
                        "affichée mais moins fiable — même convention que le scatter plot principal."
                    )

ranking_unit_label = "% du plafond" if is_all_seasons else "M$"
team_ranking_title = f"📊 Classement des équipes par valeur ajoutée cumulée ({ranking_unit_label})"
if is_all_seasons:
    team_ranking_title += " — toutes saisons"
with st.expander(team_ranking_title):
    if team_ranking_df.empty:
        st.info("Aucune donnée de valeur ajoutée disponible pour construire ce classement.")
    else:
        team_agg = (
            team_ranking_df.groupby("team")[ranking_value_col]
            .agg(total_value_added="sum", n_players="count")
            .reset_index()
        )
        team_agg["avg_value_added"] = team_agg["total_value_added"] / team_agg["n_players"]
        # ascending=True : avec des barres horizontales, Plotly dessine la 1re ligne du
        # DataFrame en bas — donc trier croissant place l'équipe la plus sous-payée collectivement
        # (valeur la plus haute) tout en haut du graph, comme demandé.
        team_agg = team_agg.sort_values("total_value_added", ascending=True)

        # Badge 🏆 champion NBA : récompense COLLECTIVE (tout le roster), affichée sur l'équipe
        # dans ce classement plutôt qu'en icône sur un point individuel du scatter (voir
        # SEASON_AWARDS pour les récompenses individuelles). champions_by_season est optionnel
        # sur SportConfig (None pour un sport sans cette donnée) -- {} en repli, aucune icône,
        # pas de crash. ranking_seasons = saisons effectivement représentées par CE classement
        # (une seule en mode saison unique, toutes en mode "Toutes les saisons").
        champions_by_season = sport.champions_by_season or {}
        ranking_seasons = ALL_SEASONS_KEYS if is_all_seasons else [season]
        team_titles: dict[str, list[str]] = {}
        for s in ranking_seasons:
            champ = champions_by_season.get(s)
            if champ:
                team_titles.setdefault(champ, []).append(s)
        team_agg["team_label"] = team_agg["team"].map(
            lambda t: f"🏆 {t}" if t in team_titles else t
        )

        axis_label = f"Valeur ajoutée cumulée ({ranking_unit_label})"
        fig_teams = px.bar(
            team_agg,
            x="total_value_added",
            y="team_label",
            orientation="h",
            color="total_value_added",
            color_continuous_scale="RdYlGn",
            custom_data=["n_players", "avg_value_added"],
            labels={"total_value_added": axis_label, "team_label": ""},
            template="plotly_white",
            height=max(400, min(900, 28 * len(team_agg) + 120)),
        )
        players_label = "Participations (saison x joueur)" if is_all_seasons else "Joueurs comptés"
        # Format d3 différent selon l'unité : ",.1%" (pourcentage, mode toutes saisons) vs
        # ",.1f" M$ (mode saison unique) — même bascule que ranking_value_col ci-dessus.
        value_fmt = ",.1%" if is_all_seasons else ",.1f"
        unit_suffix = "" if is_all_seasons else " M$"

        def _team_hovertemplate(team: str) -> str:
            # Un hovertemplate PAR POINT (liste, pas une chaîne unique) plutôt qu'un template
            # commun avec une ligne vide conditionnelle : la ligne 🏆 n'apparaît que pour les
            # équipes réellement titrées, pas de ligne fantôme pour les autres.
            lines = [
                "<b>%{y}</b>",
                f"Valeur ajoutée cumulée : %{{x:{value_fmt}}}{unit_suffix}",
                f"{players_label} : %{{customdata[0]}}",
                f"Moyenne par joueur : %{{customdata[1]:{value_fmt}}}{unit_suffix}",
            ]
            titles = team_titles.get(team, [])
            if titles:
                lines.append(
                    f"🏆 Championne NBA : {len(titles)} saison(s) sur la période affichée"
                    if is_all_seasons else f"🏆 Championne NBA {titles[0]}"
                )
            return "<br>".join(lines) + "<extra></extra>"

        fig_teams.update_traces(
            hovertemplate=[_team_hovertemplate(t) for t in team_agg["team"]]
        )
        fig_teams.update_layout(
            coloraxis_showscale=False,
            xaxis_title=axis_label,
            xaxis_tickformat=".0%" if is_all_seasons else None,
            yaxis_title="",
            margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig_teams, width='stretch')
        ranking_caption = (
            "Respecte les filtres \"Minutes par match minimum\" et \"Nombre de matchs joués "
            "minimum\" de la sidebar, mais ignore volontairement \"Filtrer par équipe\" — sinon "
            "il ne resterait qu'une ou deux équipes à classer."
        )
        if team_titles:
            ranking_caption += " 🏆 = équipe championne NBA sur la période affichée."
        if is_all_seasons:
            ranking_caption += (
                " Mode \"Toutes les saisons\" : les valeurs sont en % du plafond salarial de "
                "chaque saison (comparable dans le temps, contrairement au `$` brut) et cumulées "
                "sur toute la période — \"Participations\" (dans l'infobulle) compte les "
                "apparitions saison par saison, pas des joueurs uniques (un joueur présent "
                "plusieurs saisons compte une fois par saison jouée)."
            )
        st.caption(ranking_caption)
