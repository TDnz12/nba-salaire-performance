"""
Mercato — composition à 6 joueurs (5 majeur + 6e homme) de chaque équipe pour la saison
sélectionnée, une carte par équipe, mise en page HORIZONTALE (tuiles photo côte à côte, sur le
modèle du roster builder de rostermania.com — Call of Duty League). Page séparée du dashboard
principal (Dashboard.py, qui ne change pas de comportement), même convention que
pages/1_Radar_de_comparaison.py et pages/2_Rosters.py : script Streamlit à part entière (système
multi-page natif basé sur le dossier pages/), qui partage st.session_state avec les autres pages
sans les importer.

v3 (cette étape, mise en page horizontale) : EN LECTURE SEULE. Aucun bouton, aucune interaction
-- la logique de données complète (éligibilité, tri, étiquettes M/A/AI/AF/P) vit dans
nba.get_mercato_lineup, voir sa docstring pour le détail. Retrait/ajout/swap/reset viendront aux
étapes suivantes -- déjà prévu structurellement :
  - chaque tuile joueur est dans sa PROPRE colonne Streamlit (st.columns, une par slot + une
    colonne d'espacement entre le 5e slot et le 6e homme), avec sous la tuile un emplacement
    réservé pour une future barre de boutons (retirer / intervertir avec le slot de droite) ;
  - l'en-tête de carte réserve sa partie droite pour un futur bouton "réinitialiser" ;
  - un bouton Streamlit ne peut de toute façon pas vivre à l'intérieur d'un bloc HTML injecté
    via st.markdown(unsafe_allow_html=True), d'où ce découpage en colonnes dès maintenant plutôt
    que de la mise en page HTML pure.

2 cartes par ligne (pas 3, voir la v2 précédente) : à 6 tuiles par carte (contre 4 sur
rostermania), il faut de la largeur pour que les photos restent grandes. Responsive : st.columns
empile nativement ses colonnes sur écran étroit (comportement Streamlit standard, pas de media
query ajoutée ici) -- sur téléphone, les 2 cartes passent l'une sous l'autre, et à l'intérieur de
chaque carte les 6 tuiles passent aussi en pile verticale plutôt que d'être écrasées côte à côte
: chaque tuile reste donc lisible même très étroite (pas vérifié sur un vrai téléphone, cette
page n'ayant pas de navigateur mobile à disposition ici -- à confirmer visuellement).

Duplique volontairement le bloc CSS de densité et les petits helpers (_img_html, gabarits d'URL
CDN) de pages/2_Rosters.py plutôt que de les importer -- un fichier de pages/ est un script à
part entière, pas un module (voir la docstring de pages/1_Radar_de_comparaison.py pour le
pourquoi). Contrairement à Rosters, pas de script de remise à zéro du scroll : cette page n'a
qu'une seule vue, pas de bascule grille/roster qui laisserait le scroll mal placé après un rerun.

Identité d'équipe par saison (nom affiché + décision logo actuel vs emblème neutre) : voir
team_logo_url() plus bas et nba.get_team_identity pour le détail complet (piège des franchises
ayant déménagé/changé de nom depuis 1996-97, ex: Seattle SuperSonics -> Oklahoma City Thunder,
même team_id, nom différent -- CHA 2004-05 = Charlotte Bobcats, même abréviation ET même team_id
que les Hornets actuels mais nom différent aussi).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data_sources import SPORTS

st.set_page_config(page_title="Mercato — Sports Analytics", page_icon="🔄", layout="wide")

# Même bloc de densité que Dashboard.py / pages/1_Radar_de_comparaison.py / pages/2_Rosters.py
# (copié tel quel, voir leur commentaire d'origine pour le détail de chaque règle) -- seul le
# texte du titre (stLogoSpacer::before) change, ci-dessous. Les classes .roster-logo-box/
# .roster-photo-box et la règle sur les boutons sont copiées telles quelles mais ne servent pas
# ici (page sans bouton visible) ; les classes propres à cette page (tuiles, en-tête de carte)
# sont ajoutées dans le second bloc <style> plus bas.
st.markdown(
    """
    <style>
    header[data-testid="stHeader"] {
        height: 2.25rem !important;
        min-height: 2.25rem !important;
    }
    div[data-testid="stSidebarHeader"] {
        height: 2.25rem !important;
        min-height: 0 !important;
        padding-top: 0.25rem !important;
        padding-bottom: 0.25rem !important;
    }
    div[data-testid="stLogoSpacer"] {
        width: auto !important;
        display: flex;
        align-items: center;
    }
    div[data-testid="stLogoSpacer"]::before {
        content: "🔄 Mercato";
        font-weight: 700;
        font-size: 1rem;
        white-space: nowrap;
    }
    div[data-testid="stAppViewBlockContainer"], .block-container {
        padding-top: 1.25rem !important;
        /* Marges latérales réduites SUR CETTE PAGE UNIQUEMENT (ce bloc <style> est propre à
           Mercato, pas partagé avec Dashboard.py/Rosters/Radar) -- pour laisser le plus de
           largeur possible aux tuiles (2 cartes x 6 tuiles/carte, voir demande). */
        padding-left: 1.25rem !important;
        padding-right: 1.25rem !important;
        max-width: 100% !important;
    }
    div[data-testid="stAppViewBlockContainer"] h1:first-of-type {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    div[data-testid="stSidebarNav"] {
        padding-top: 0.2rem;
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
        gap: 0.25rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stElementContainer"] {
        margin-bottom: 0.1rem !important;
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
        margin: 1rem 0 !important;
    }
    .roster-logo-box, .roster-photo-box {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        background: transparent;
    }
    .roster-logo-box { height: 110px; }
    .roster-photo-box { height: 140px; }
    .roster-logo-box img, .roster-photo-box img {
        width: 100%;
        height: 100%;
        object-fit: contain;
    }
    div[data-testid="stButton"] button {
        min-height: 2.75rem;
        white-space: normal;
        line-height: 1.2;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Classes propres à cette page. .mercato-tile-* : tuile joueur façon rostermania.com -- photo qui
# REMPLIT le cadre (object-fit: cover, contrairement à .roster-photo-box qui utilise "contain"
# ailleurs dans le projet -- choix délibéré ici, demandé pour ce style de tuile), fond sombre
# neutre derrière (visible sur les zones transparentes/le temps du chargement, ou si la photo est
# manquante -- voir la limite déjà acceptée sur pages/2_Rosters.py), coins arrondis, badge de
# poste en haut à gauche, ⚠️ éventuel en haut à droite, nom de famille en surimpression en bas sur
# un dégradé sombre pour rester lisible quelle que soit la photo. .mercato-team-emblem : repli
# neutre (cercle gris + abréviation) quand le logo actuel de la franchise ne correspond PAS à son
# identité cette saison-là (voir team_logo_url plus bas).
st.markdown(
    """
    <style>
    .mercato-card-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .mercato-team-logo-box {
        width: 32px;
        height: 32px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .mercato-team-logo-box img {
        width: 100%;
        height: 100%;
        object-fit: contain;
    }
    .mercato-team-emblem {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: rgba(128, 128, 128, 0.35);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.62rem;
        font-weight: 700;
        flex-shrink: 0;
    }
    .mercato-team-name {
        font-weight: 700;
        font-size: 1rem;
    }
    .mercato-tile-wrap {
        position: relative;
        width: 100%;
        aspect-ratio: 3 / 4;
        border-radius: 0.6rem;
        overflow: hidden;
        background: #1c1c1c;
        margin-top: 0.5rem;
        /* Marge basse égale à la marge latérale du conteneur de carte (repéré en test : le nom
           en surimpression touchait presque la bordure basse de la carte sans elle -- Streamlit
           ne laisse pas de marge propre après la dernière rangée de colonnes). */
        margin-bottom: 0.75rem;
    }
    .mercato-tile-wrap img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        /* Cadré en haut (pas centré verticalement, la valeur par défaut) : le visage/les
           épaules restent visibles sans être rognés par le haut du cadre ni redescendre sous le
           nom en surimpression tout en bas (voir .mercato-tile-name). */
        object-position: center top;
        display: block;
    }
    .mercato-tile-badge {
        position: absolute;
        top: 0.25rem;
        left: 0.25rem;
        background: #1f77b4;
        color: #fff;
        font-weight: 700;
        font-size: 0.65rem;
        padding: 0.08rem 0.32rem;
        border-radius: 0.3rem;
        z-index: 2;
    }
    .mercato-tile-warning {
        position: absolute;
        top: 0.15rem;
        right: 0.3rem;
        font-size: 0.85rem;
        z-index: 2;
        cursor: help;
    }
    .mercato-tile-name {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        padding: 1rem 0.2rem 0.25rem;
        background: linear-gradient(to top, rgba(0, 0, 0, 0.88) 15%, rgba(0, 0, 0, 0) 100%);
        color: #fff;
        font-weight: 800;
        /* Réduits (0.68rem/0.02em -> 0.56rem/0.01em) : des noms comme ALEXANDER-WALKER,
           PRITCHARD, MCCOLLUM, KNUEPPEL étaient tronqués en "..." même sur une tuile large --
           les "..." (overflow/text-overflow ci-dessous) restent en dernier recours pour les cas
           vraiment extrêmes, pas la norme. */
        font-size: 0.56rem;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# MVP : NBA uniquement, même raison que pages/1_Radar_de_comparaison.py et pages/2_Rosters.py.
sport = SPORTS["nba"]
if sport.get_mercato_lineup is None:
    st.title("🔄 Mercato")
    st.info("Mercato pas encore disponible pour ce sport.")
    st.stop()

LOGO_URL_TEMPLATE = "https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"
HEADSHOT_URL_TEMPLATE = "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"


def _img_html(url: str, alt: str, box_class: str) -> str:
    # loading="lazy" (pas "eager" comme pages/2_Rosters.py) : jusqu'à ~210 images sur cette page
    # (30 logos/emblèmes + jusqu'à 180 photos joueurs), contre 30 max sur Rosters -- lazy laisse
    # le navigateur ne charger que ce qui est visible. Sans risque de retrouver le bug de
    # Rosters (images qui disparaissaient après un rerun) : ce bug venait de la largeur en
    # "stretch" calculée après coup par le navigateur, pas du mode de chargement -- le cadre CSS
    # à taille FIXE (déjà en place ici, voir plus haut) reste le vrai fix, présent des deux
    # côtés.
    return f'<div class="{box_class}"><img src="{url}" alt="{alt}" loading="lazy" decoding="async"></div>'


NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def _last_name(full_name: str) -> str:
    parts = full_name.split()
    while parts and parts[-1].lower().rstrip(".") in NAME_SUFFIXES:
        parts.pop()
    return parts[-1] if parts else full_name


def _display_last_names(players: list[str]) -> list[str]:
    """Nom de famille en MAJUSCULES pour l'étiquette de la tuile -- si deux joueurs de la MÊME
    carte partagent le même nom de famille, préfixe l'initiale du prénom (ex: "J. WILLIAMS" /
    "M. WILLIAMS") pour les distinguer. Le nom complet reste disponible en info-bulle (attribut
    title sur la tuile, voir _tile_html) quel que soit le cas."""
    last_names = [_last_name(p) for p in players]
    counts: dict[str, int] = {}
    for ln in last_names:
        counts[ln.lower()] = counts.get(ln.lower(), 0) + 1
    result = []
    for full, ln in zip(players, last_names):
        if counts[ln.lower()] > 1 and full.strip():
            result.append(f"{full.strip()[0]}. {ln}".upper())
        else:
            result.append(ln.upper())
    return result


def _tile_html(row: pd.Series, display_name: str) -> str:
    img_tag = (
        f'<img src="{HEADSHOT_URL_TEMPLATE.format(player_id=int(row["player_id"]))}" '
        f'alt="{row["player"]}" loading="lazy" decoding="async">'
        if pd.notna(row["player_id"]) else ""
    )
    warning_html = (
        '<span class="mercato-tile-warning" '
        'title="Poste inconnu dans les données : étiquette approximative">⚠️</span>'
        if row["position_missing"] else ""
    )
    return (
        f'<div class="mercato-tile-wrap" title="{row["player"]}">'
        f'{img_tag}'
        f'<span class="mercato-tile-badge">{row["label"]}</span>'
        f'{warning_html}'
        f'<div class="mercato-tile-name">{display_name}</div>'
        f'</div>'
    )


teams_static = sport.get_teams_static() if sport.get_teams_static else []
team_by_id = {t["id"]: t for t in teams_static}


def _normalize_team_name(name: str) -> str:
    # nba_api abrège parfois la ville en "LA" (ex: "LA Clippers") alors que get_teams_static()
    # (nba_api.stats.static.teams) écrit toujours la ville en toutes lettres ("Los Angeles
    # Clippers") -- pure différence d'écriture, PAS un changement d'identité de franchise.
    # Repéré en comparant les 30 équipes de la saison la plus récente à get_teams_static() :
    # seul ce cas apparaît (les 29 autres correspondent déjà exactement). Ciblé sur le préfixe
    # "LA " précisément plutôt que sur le seul surnom : comparer par surnom seul laisserait
    # passer à tort "New Jersey Nets" pour "Brooklyn Nets" (le surnom "Nets" ne change pas alors
    # que la ville/l'identité, si).
    return "Los Angeles " + name[3:] if name.startswith("LA ") else name


def team_logo_url(team_code: str, season: str, identity: dict) -> str | None:
    """Logo NBA de `team_code` pour `season`, UNIQUEMENT si l'identité de cette saison-là
    (team_id + nom, voir `identity` = nba.get_team_identity) est celle de la franchise ACTUELLE
    (même ville, même nom qu'aujourd'hui, à l'écriture "LA"/"Los Angeles" près -- voir
    _normalize_team_name) -- sinon None, l'appelant doit alors afficher un emblème neutre,
    JAMAIS le logo actuel d'une franchise qui portait un autre nom cette saison-là (ex: CHA
    2004-05 = Charlotte Bobcats, même team_id que les Hornets actuels mais nom différent -- pas
    de logo). Fonction isolée : un futur logo historique par époque (ex: le vrai logo des
    SuperSonics) se branche ici uniquement, sans toucher au reste de la page NI à
    pages/2_Rosters.py une fois cette fonction partagée."""
    info = identity.get(team_code)
    if info is None:
        return None
    team_id, team_name_this_season = info
    current = team_by_id.get(team_id)
    if current is None or current["full_name"] != _normalize_team_name(team_name_this_season):
        return None
    return LOGO_URL_TEMPLATE.format(team_id=team_id)


# Saison : même sélecteur que pages/2_Rosters.py, aligné par défaut sur la saison actuellement
# affichée dans la sidebar principale de Dashboard.py (st.session_state["main_season"], partagé
# -- voir son commentaire) si elle est valide ici (une vraie saison, pas le mode combiné "Toutes
# les saisons" qui n'a pas d'équivalent sur cette page). key= (pas index= recalculé) pour que le
# choix de l'utilisateur SUR CETTE PAGE survive aux reruns suivants, même principe que
# rosters_season/radar_season. Toujours la saison régulière (get_mercato_lineup ne gère que ça,
# voir sa docstring).
_default_season = "2024-25" if "2024-25" in sport.seasons else sport.seasons[0]
if "mercato_season" not in st.session_state:
    _main_season = st.session_state.get("main_season")
    st.session_state["mercato_season"] = _main_season if _main_season in sport.seasons else _default_season
season = st.sidebar.selectbox("Saison", options=sport.seasons, key="mercato_season")


@st.cache_data(show_spinner="Chargement de la composition Mercato...")
def load_mercato(sport_key: str, season: str) -> pd.DataFrame:
    return SPORTS[sport_key].get_mercato_lineup(season, force_refresh=False)


@st.cache_data(show_spinner=False)
def load_team_identity(sport_key: str, season: str) -> pd.DataFrame:
    getter = SPORTS[sport_key].get_team_identity
    if getter is None:
        return pd.DataFrame(columns=["team", "team_id", "team_name"])
    return getter(season, force_refresh=False)


try:
    df = load_mercato(sport.key, season)
except Exception as exc:
    st.error(f"Impossible de charger la composition Mercato pour {season} : {exc}")
    st.stop()

if df.empty:
    st.warning(f"Aucune donnée disponible pour {season}.")
    st.stop()

identity_df = load_team_identity(sport.key, season)
identity = {r["team"]: (r["team_id"], r["team_name"]) for _, r in identity_df.iterrows()}


def _team_display_name(team_code: str) -> str:
    info = identity.get(team_code)
    return info[1] if info else team_code


st.title("🔄 Mercato")
st.caption(f"Composition à 6 joueurs par équipe — saison régulière {season}.")

team_abbrevs = sorted(df["team"].unique(), key=_team_display_name)

# 7 colonnes par carte : slots 1-5 (indices 0-4), une colonne d'espacement étroite (index 5,
# jamais remplie -- sépare visuellement le 5 majeur du 6e homme, réduite à 0.15 -- juste assez
# pour rester visible sans manger de largeur aux tuiles, voir demande), puis le 6e homme
# (index 6).
SLOT_COL_WIDTHS = [1, 1, 1, 1, 1, 0.15, 1]

N_COLS = 2
cols = st.columns(N_COLS)
for i, abbrev in enumerate(team_abbrevs):
    team_name = _team_display_name(abbrev)
    logo_url = team_logo_url(abbrev, season, identity)
    team_rows = df[df["team"] == abbrev].sort_values("slot").reset_index(drop=True)
    display_names = _display_last_names(team_rows["player"].tolist())

    with cols[i % N_COLS]:
        with st.container(border=True):
            # En-tête : logo/emblème + nom à gauche, colonne étroite réservée au futur bouton
            # "réinitialiser" à droite (rien d'affiché pour l'instant).
            header_col, reset_col = st.columns([6, 1])
            with header_col:
                header_html = '<div class="mercato-card-header">'
                if logo_url:
                    header_html += _img_html(logo_url, abbrev, "mercato-team-logo-box")
                else:
                    header_html += f'<div class="mercato-team-emblem">{abbrev}</div>'
                header_html += f'<span class="mercato-team-name">{team_name}</span></div>'
                st.markdown(header_html, unsafe_allow_html=True)
            with reset_col:
                pass  # réservé au futur bouton "réinitialiser l'équipe" (étape 3)

            # gap="xxsmall" (plus serré que le "small" par défaut de st.columns) : resserre
            # l'espace entre tuiles pour leur laisser plus de largeur, voir demande.
            slot_cols = st.columns(SLOT_COL_WIDTHS, gap="xxsmall")
            for j, row in team_rows.iterrows():
                col_idx = j if j < 5 else j + 1  # saute la colonne d'espacement (index 5)
                with slot_cols[col_idx]:
                    st.markdown(_tile_html(row, display_names[j]), unsafe_allow_html=True)
                    # Réservé à la future barre de boutons (retirer / intervertir avec le slot
                    # de droite, étape 3) -- chaque tuile est déjà dans sa propre colonne
                    # Streamlit pour ça, rien d'affiché ici pour l'instant.

st.caption(
    "Composition = 6 joueurs avec le plus de minutes par match dans leur équipe de fin de "
    "saison, en ne comptant que les matchs joués avec cette équipe (seuils minimum de matchs "
    "pour écarter les petits échantillons). Étiquettes de poste attribuées dans l'ordre "
    "M/A/AI/AF/P après tri par groupe de poste (Extérieur, Ailier, Intérieur) : elles peuvent "
    "ne pas correspondre au poste exact du joueur. Le 5 majeur correspond aux 5 joueurs les "
    "plus utilisés, pas forcément au 5 de départ officiel."
)
