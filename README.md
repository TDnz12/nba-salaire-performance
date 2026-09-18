# Sports Analytics Dashboard

Dashboard interactif Streamlit pour explorer les stats sportives. **MVP : Basketball (NBA) uniquement**, architecture prête pour ajouter rugby / foot / MMA / tennis sans toucher au dashboard.

## Installation

> ⚠️ **Ne crée pas le `.venv` dans ce dossier** si ton `~/Desktop` ou `~/Documents` est
> synchronisé avec iCloud Drive (réglage macOS "Bureau et Documents" activé). iCloud évince
> les fichiers rarement utilisés vers le cloud ("Optimiser le stockage Mac"), et un
> environnement virtuel Python (des milliers de petits fichiers) s'y fait évincer en
> permanence : chaque lancement à froid peut alors prendre plusieurs **minutes** (constaté :
> un simple `import streamlit` est passé de 1,4 s à 374 s, avec parfois des erreurs
> `OSError: Operation canceled` en pleine lecture). On met donc le `.venv` hors d'iCloud,
> ailleurs sous `~/` :

```bash
python3 -m venv ~/.venvs/sports-analytics-claude
source ~/.venvs/sports-analytics-claude/bin/activate
pip install -r requirements.txt
```

Le code du projet, lui, peut rester sur le Bureau sans souci (peu de fichiers, gros CSV mis
en cache dans `data_cache/` exclu du sync — voir `.gitignore`).

## Configurer l'accès aux datasets Kaggle (salaires + PER)

Les stats de jeu viennent de `nba_api` (aucune config nécessaire). Le **salaire** vient de
**deux** datasets Kaggle distincts, dispatchés automatiquement selon la saison — voir
`data_sources/nba.RATIN21_DATASET_START_YEAR` pour la frontière exacte dans le code :

| Saisons | Dataset | Détails |
|---|---|---|
| 2010-11 → saison courante | [`ratin21/nba-player-stats-and-salaries-2010-2025`](https://www.kaggle.com/datasets/ratin21/nba-player-stats-and-salaries-2010-2025) | Colonnes `Player, Salary, Year, ...`. Pas de PER dans ce dataset, d'où l'usage du PIE de nba_api comme métrique d'efficacité/valeur. En prod depuis le début du projet. |
| 1996-97 → 2009-10 | [`iampunitkmryh/nba-players-details-198518`](https://www.kaggle.com/datasets/iampunitkmryh/nba-players-details-198518) (`salaries_1985to2018.csv` + `players.csv`, licence **CC0**) | Comble le trou que ratin21 ne couvre pas. Deux fichiers fusionnés sur `player_id` (voir `_load_legacy_kaggle_raw` dans `data_sources/nba.py`). |

1996-97 est la borne basse absolue du dashboard : c'est la première saison où `nba_api` renvoie
des données exploitables (testé empiriquement — 1995-96 renvoie 0 ligne sans erreur, 1996-97 en
renvoie 441 ; voir `EARLIEST_SUPPORTED_SEASON_START_YEAR`), donc antérieur à ça il n'y aurait de
toute façon pas de stats de jeu à croiser avec un éventuel salaire.

Le dataset legacy a deux trous de couverture connus et documentés (`KNOWN_SALARY_DATA_GAPS` dans
`data_sources/nba.py`) : **1986-87** et **1989-90**. Ils sont hors de la plage réellement utilisée
par le dashboard (1996-97+), donc sans impact concret aujourd'hui — la liste est simplement
conservée au cas où la borne basse serait un jour repoussée plus loin dans le passé.

Deux options pour obtenir chaque dataset, gratuites toutes les deux :

**Option A — automatique (recommandé)**
1. Crée un compte gratuit sur [kaggle.com](https://www.kaggle.com) si besoin.
2. Va dans *Settings* → *API* → *Create New Token* → télécharge `kaggle.json`.
3. Place-le dans `~/.kaggle/kaggle.json` (`chmod 600 ~/.kaggle/kaggle.json`).
4. Lance l'app normalement : chaque dataset est téléchargé une seule fois puis mis en cache dans `data_cache/`.

**Option B — manuelle (sans compte configuré côté machine)**
1. Télécharge le(s) CSV depuis la page du dataset concerné (bouton *Download*) :
   [ratin21](https://www.kaggle.com/datasets/ratin21/nba-player-stats-and-salaries-2010-2025) ou
   [iampunitkmryh](https://www.kaggle.com/datasets/iampunitkmryh/nba-players-details-198518).
2. Dézippe et dépose les `.csv` dans `data_cache/raw/nba/manual/` (ratin21) ou
   `data_cache/raw/nba/manual_legacy/` (dataset legacy — les deux fichiers `salaries_1985to2018.csv`
   ET `players.csv` sont nécessaires).
3. Relance l'app — elle détecte automatiquement les fichiers.

Si aucune des deux n'est faite pour une saison donnée, le dashboard fonctionne quand même (stats
de jeu via nba_api) mais les colonnes Salaire / Valeur seront vides pour cette saison, avec un
avertissement affiché dans l'UI.

> Note : ce test a déjà été effectué avec succès pendant le développement pour les deux datasets —
> `kagglehub` les a téléchargés **sans aucune configuration**, tous deux étant publics. La config
> Kaggle ci-dessus ne devrait donc être nécessaire que si Kaggle change sa politique d'accès
> anonyme.

### Normalisation en % du plafond salarial

Le plafond salarial officiel de la NBA (salary cap) a été multiplié par plus de 6 entre 1996-97
(24,4 M$) et 2025-26 (154,6 M$) — comparer des montants en $ bruts entre saisons aussi éloignées
n'a donc pas grand sens. Le dashboard calcule en plus, pour chaque saison, `salary_pct_cap`,
`expected_salary_pct_cap` et `value_added_pct_cap` (salaire / salaire attendu / valeur ajoutée,
exprimés en % du plafond de la saison), via la table `NBA_SALARY_CAP_BY_SEASON` dans
`data_sources/nba.py`. Source : table de plafonds historiques publiée par SalarySwish,
recoupée avec succès pour 11 des 30 saisons (1996-97 à 1999-00 et 2016-17 à 2025-26) contre des
chiffres indépendants (ESPN, pr.nba.com). Ces 3 métriques sont sélectionnables comme n'importe
quelle autre dans les listes X/Y/Couleur/Taille du dashboard.

## Lancer le dashboard

```bash
streamlit run app.py
```

## Pré-remplir le cache (optionnel)

Le dashboard couvre 30 saisons (1996-97 → 2025-26, voir `data_sources/nba.SEASONS`). Par défaut,
chaque saison est calculée (et mise en cache) au premier chargement par un utilisateur — un peu
lent la toute première fois qu'une saison donnée est demandée. Pour éviter ça (ex: avant une démo,
ou après un déploiement), un script dédié parcourt toutes les saisons à l'avance :

```bash
PYTHONPATH=. python scripts/prefill_cache.py            # ne recalcule que les saisons pas encore en cache
PYTHONPATH=. python scripts/prefill_cache.py --force     # recalcule tout, y compris ce qui est déjà en cache
```

N'interrompt pas le run entier si une saison échoue (panne réseau ponctuelle, rate-limit
stats.nba.com...) : l'erreur est loguée, le script continue avec la saison suivante, et un résumé
final liste les échecs. Relancer le script sans `--force` ne retente que les saisons manquantes.

## Architecture

```
app.py                       # UI Streamlit uniquement — ne connaît que data_sources.SPORTS
data_sources/
  __init__.py                 # registre SPORTS = {"nba": ..., "rugby": (bientôt), ...}
  base.py                     # schéma commun, Metric, normalize_name(), cache parquet
  nba.py                      # get_player_stats(season), SEASONS, METRICS pour la NBA
data_cache/
  raw/nba/                    # fichiers bruts (CSV Kaggle x2, réponses nba_api par saison)
  processed/nba/              # DataFrame normalisé final, en cache par saison (parquet)
scripts/
  prefill_cache.py            # pré-remplit le cache pour toutes les saisons (voir plus haut)
```

### Ajouter un nouveau sport (ex: rugby)

1. Crée `data_sources/rugby.py` avec :
   - `SEASONS: list[str]`
   - `METRICS: dict[str, Metric]` (voir `base.Metric`)
   - `get_player_stats(season: str, force_refresh: bool = False) -> pd.DataFrame` retournant
     au minimum les colonnes `sport, season, player, team` + les clés de `METRICS`.
2. Dans `data_sources/__init__.py`, remplace l'entrée `RUGBY = SportConfig(..., available=False)`
   par une entrée pointant vers ce module (`available=True`, `get_player_stats=rugby.get_player_stats`, etc.).
3. Rien à changer dans `app.py` — le sélecteur de sport, les listes de saisons/métriques et le
   scatter plot se construisent automatiquement à partir du registre.

## Sources de données — pourquoi ce choix

- **`nba_api`** (stats de jeu) : consomme directement les endpoints JSON officiels de
  stats.nba.com, gratuit, sans clé, activement maintenu. Préféré à un scraping HTML.
- **Basketball-Reference** : volontairement **pas** scrapé automatiquement — leurs
  [Terms of Use](https://www.sports-reference.com/termsofuse.html) interdisent l'usage de bots/scrapers
  sans autorisation écrite, et un rate-limit strict (~20 req/min) est appliqué. On récupère les
  salaires via le dataset Kaggle qui en est sourcé, plutôt que de scraper directement le site.
  Ce dataset ne fournit pas le PER (métrique propriétaire calculée par Basketball-Reference) ;
  le dashboard utilise à la place le **PIE** (Player Impact Estimate), une métrique d'efficacité
  officielle NBA fournie nativement par nba_api.
- **Spotrac** : écarté — protection Cloudflare active (403 sur robots.txt), peu fiable à scraper.
- **HoopsHype** : écarté pour le MVP au profit du dataset Kaggle (fiabilité, pas de dépendance
  à la structure HTML d'un site tiers qui peut changer). `requests` + `beautifulsoup4` restent
  dans les dépendances si on veut ajouter un scraping léger de complément plus tard (ex:
  rafraîchir les salaires de la saison en cours avant que le dataset Kaggle ne soit mis à jour).

## Valeur ajoutée (salaire attendu vs réel)

`data_sources/base.compute_value_added(df, salary_col, performance_cols, fit_mask=...)` ajuste
une régression linéaire simple (scikit-learn) `salaire ~ performance`, puis calcule pour
chaque joueur :
- `expected_salary` : le salaire que le modèle "attend" compte tenu de sa performance ;
- `value_added` = `expected_salary - salaire_réel` : positif = joueur sous-payé par rapport
  à sa perf (bonne affaire), négatif = surpayé.

Fonction générique et indépendante du sport (ne connaît que des noms de colonnes) — un futur
`data_sources/rugby.py` peut l'appeler tel quel avec ses propres colonnes de performance et son
propre `fit_mask`, sans dupliquer la logique de régression.

**Pour la NBA, les variables explicatives sont PIE + "impact hors scoring"** (rebonds + contres +
passes + interceptions par match — `VALUE_ADDED_PERFORMANCE_COLS` dans `data_sources/nba.py`).
Deux étapes précédentes, gardées ici pour comprendre le raisonnement :

1. **PIE seul** (éviter de compter le scoring deux fois, sa formule l'intègre déjà) : dégradait
   le modèle (R² 0.58→0.18) et faisait *baisser* le salaire attendu de Wembanyama au lieu de le
   faire monter — le marché NBA récompense réellement le volume de scoring au-delà de ce que le
   PIE seul capture. Abandonné.
2. **PIE + points/match, ajusté sur les vétérans uniquement** (`get_player_stats` calcule
   l'ancienneté de chaque joueur via `_fetch_nba_api_experience` — endpoint `CommonAllPlayers` de
   nba_api, fonctionne aussi pour les non-draftés comme Alex Caruso contrairement à `DRAFT_YEAR`
   qui vaut "Undrafted" pour eux — et exclut du fit les `ROOKIE_SCALE_MAX_YEARS = 4` premières
   saisons, dont le salaire est fixé par la convention collective et pas négocié au marché) :
   corrige bien le biais rookie (R² 0.58→0.68 sur 2023-24), mais révèle un second problème — PIE
   et points/match sont corrélés à ~0.74 chez les vétérans, cette colinéarité rendait le
   coefficient de PIE **négatif** (-22.9M$/unité, un artefact statistique). Une régression Ridge
   (alpha choisi par validation croisée) ne corrige pas le signe : la CV optimise l'erreur de
   prédiction, pas l'interprétabilité, et garde ce qui marche même si c'est un artefact.
3. **PIE + impact hors scoring (version actuelle)** : règle le problème de cohérence — les deux
   coefficients ressortent positifs, et sur 27895+ paires de vétérans où un joueur domine
   strictement un autre sur les deux variables, on passe de 753 violations (PIE+PTS) à 1 seule.
   Coût : R² plus bas (0.31 vs 0.50 sur 2025-26) puisque le scoring, meilleur prédicteur du
   salaire réel, est volontairement exclu au profit d'un classement "valeur ajoutée" cohérent.

**Filtre sur le nombre de matchs joués (`MIN_GAMES_FOR_FIT = 15`)** : un joueur avec très peu de
matchs (ex: 4-11) peut avoir une moyenne par match gonflée par un simple coup de chaud plutôt
qu'une vraie performance de saison — même risque que les rookies, sur un axe différent. Ces
joueurs sont donc **exclus du fit** (`fit_mask` combine `~is_rookie_scale` et
`~low_sample_size`) mais **pas de l'affichage** : ils reçoivent quand même un salaire attendu
(prédit à partir de la ligne de marché ajustée sur les autres), et `app.py` les distingue
visuellement dans le scatter plot (losange plutôt que rond, même remplissage coloré que le
reste du graph — seule la forme change, badge dans le tableau détaillé) via la colonne
`low_sample_size`, sans les cacher du classement. Un second slider dans la sidebar ("Nombre de
matchs joués minimum") permet, à l'inverse, de les filtrer manuellement si besoin — par défaut
à 0 pour ne rien cacher.

Le R² du modèle (calculé sur le sous-ensemble d'ajustement) et sa taille d'échantillon sont
affichés dans l'UI (légende sous le graphique) dès que `expected_salary_musd` ou
`value_added_musd` est sélectionné. C'est un modèle simple à but exploratoire, pas une évaluation
contractuelle réelle.

## Biais de sous-valorisation des scoreurs purs (limite connue, investiguée et conservée)

Repéré en examinant Michael Jordan en 1996-97 (82 matchs, saison quasi historique des Bulls à
69-13) : son salaire attendu ne ressortait qu'à ~25,6% du plafond de l'époque, nettement plus bas
que des profils "all-around"/intérieurs de la même saison (Shaquille O'Neal, 29,4%) malgré un PIE
au 99,3ᵉ percentile de la ligue cette saison-là.

**Diagnostic** : sur la batterie Michael Jordan / Stephen Curry / Kevin Durant / Bradley Beal
(scoreurs purs) vs Shaquille O'Neal / Tim Duncan / Giannis Antetokounmpo / Nikola Jokić
(all-around/intérieurs), sur 4 saisons couvrant deux ères (1996-97, 1999-00, 2002-03, 2023-24), un
test statistique — même méthodologie que le test de biais de poste plus haut : régression OLS de
`value_added` sur des dummies de tercile "part de scoring dans la production hors salaire",
échantillon de fit, référence = groupe intermédiaire — confirme un biais significatif (p<0.05)
sur **2 des 4 saisons testées**, dont 2023-24 (244 joueurs, p=0.0001, le test le plus puissant des
quatre).

**Trois pistes de correction testées, toutes rejetées** :
1. **PIE seul** (retour à la configuration d'avant `impact_hors_scoring`) : le biais persiste sur
   exactement les 2 mêmes saisons, avec un ordre de grandeur comparable — la preuve que ce biais
   n'est **pas** un artefact de la construction d'`impact_hors_scoring` : il est déjà présent dans
   PIE seul. Coût : R² en baisse de ~25% en moyenne sur les 4 saisons, sans aucun gain de
   neutralité en échange.
2. **PIE + une variable vérifiée non corrélée au poste** (`net_rating`, l'efficacité nette
   d'équipe sur le terrain, pas une stat de comptage) : la vérification préalable demandée est
   passée avec succès (R² d'une régression poste-seul sur `net_rating` : 0.001 à 0.02 selon la
   saison, contre un R² et une significativité nettement plus élevés pour `impact_hors_scoring`
   lors du diagnostic de biais de poste). Mais une fois combinée à PIE, `net_rating` s'avère
   statistiquement **inerte** : coefficient de quelques dizaines de milliers de $/unité seulement,
   gain de R² < 0.002 — mêmes 2 saisons biaisées, mêmes coefficients de biais à 2-3% près qu'avec
   PIE seul. Neutre côté poste, mais sans signal exploitable une fois PIE déjà dans le modèle.
3. **`impact_hors_scoring` à poids réduit (50%, appliqué après ajustement)** : ne réduit pas le
   biais de façon fiable (une saison le voit même légèrement s'aggraver, une autre fait apparaître
   un biais de poste absent à poids plein), tout en sacrifiant ~17% de R² en moyenne — un
   compromis strictement perdant, ni plus neutre ni moins coûteux qu'une des deux autres pistes.

**Interprétation retenue** : le biais ne vient pas de la construction d'`impact_hors_scoring`
puisqu'il survit intact à sa suppression complète (piste 1) et à son remplacement par une
variable non corrélée au poste (piste 2). Il s'agit plus vraisemblablement d'une caractéristique
réelle du marché salarial NBA — une prime que le marché accorde à un très haut volume de scoring,
au-delà de ce qu'une composite de statistiques de boîte à stats (PIE compris) capture — que d'un
bug de calcul. C'est une limite connue de **toute** mesure dérivée du box-score, pas spécifique à
la formule actuelle.

**Décision** : le modèle actuel (PIE + `impact_hors_scoring_zscore_poste`, poids égal — voir
section "Valeur ajoutée" ci-dessus) est conservé tel quel. Par principe du projet (voir "Sources
de données" plus haut), aucune variable hors box-score officiel n'a été envisagée comme 4ᵉ piste.
Conséquence pratique pour la lecture du dashboard : un scoreur pur à très haut volume peut
apparaître "surpayé" (`value_added` très négatif) au-delà de ce que sa valeur réelle justifierait
— un avertissement en ce sens est affiché dans l'UI (expander méthodologie), voir plus bas.

## Mode "Toutes les saisons"

En plus du sélecteur saison par saison, le dashboard propose une vue combinée ("Toutes les
saisons (1996-97 → 2025-26)" dans le sélecteur) qui charge et concatène l'intégralité de
`sport.seasons` — chaque joueur y apparaît comme un point distinct par saison jouée. Quelques
points importants :

- Un modèle salaire ~ performance **différent est ajusté séparément pour chaque saison** (pas un
  modèle unique sur 30 saisons combinées, ce qui mélangerait des marchés salariaux très
  différents) — le R²/la marge d'incertitude de chaque saison sont listés dans un tableau, dans
  l'expander méthodologie.
- La couleur du scatter plot est, par défaut, `value_added_pct_cap` (valeur ajoutée en % du
  plafond) plutôt que `value_added_musd` (M$) — comparer des $ bruts entre 1996-97 et 2025-26
  n'aurait pas de sens vu la hausse du plafond salarial (voir section normalisation plus haut). En
  mode saison unique, la couleur par défaut reste `value_added_musd`.
- Le classement des équipes (voir plus bas dans le dashboard) suit la même bascule : cumul en %
  du plafond en mode "Toutes les saisons", en M$ en mode saison unique.
- Une saison dont le modèle n'a pas pu être ajusté (ex: postes indisponibles malgré les retries)
  ou dont le salaire est indisponible n'empêche pas d'afficher les autres — un avertissement liste
  les saisons concernées plutôt que de faire échouer tout le mode combiné.

## Fiabilité (% de matchs joués, 3 dernières saisons)

Métrique `reliability_pct` = (somme des matchs joués par le joueur) / (somme des matchs
possibles de la ligue) sur la saison affichée et les `RELIABILITY_LOOKBACK_SEASONS - 1 = 2`
précédentes disponibles (`data_sources/nba._fetch_reliability`). "Matchs possibles" vient du
nombre réel de matchs joués par l'équipe qui en a joué le plus cette saison-là
(`LeagueDashTeamStats`), pas d'un 82 supposé — certaines saisons sont raccourcies (lockout
2011-12 : 66 matchs ; COVID 2019-20 : 64-75 selon l'équipe ; 2020-21 : 72 matchs). Plafonnée à
100% (quelques joueurs ressortaient légèrement au-dessus, probablement les matchs de Play-In
comptés différemment entre `LeagueDashPlayerStats` et `LeagueDashTeamStats`).

Une recrue avec moins de 3 saisons d'historique n'est sommée que sur les saisons où elle a
effectivement joué (`_seasons_lookback` s'arrête à `EARLIEST_SUPPORTED_SEASON_START_YEAR`)
plutôt que de planter ou de fausser le ratio avec des saisons inexistantes.

Mise en cache par saison, comme le reste — avec une précaution supplémentaire : si une des 3
saisons de la fenêtre échoue à se charger (ex: timeout réseau), le résultat partiel est quand
même retourné à l'appelant (pas de crash) mais **n'est volontairement pas mis en cache**, pour
ne pas figer une donnée incomplète comme si elle était définitive — le prochain chargement
retente les saisons manquantes au lieu de rester bloqué sur un résultat dégradé.

Le cache disque (`data_cache/processed/nba/`) est versionné (`PROCESSED_SCHEMA_VERSION` dans
`nba.py`) : si la logique de calcul change (nouvelle colonne, nouvelles variables de régression...),
un cache écrit sous une version différente est automatiquement ignoré et recalculé, sans besoin de
cliquer sur "Rafraîchir" à la main.

## Métrique défensive individuelle (piste abandonnée)

Une tentative a été faite pour intégrer une métrique de "défense" individuelle
au modèle (en complément de l'attaque via PIE + impact_hors_scoring), basée sur
les statistiques "hustle" disponibles via nba_api (tirs contestés, déflections,
charges provoquées).

Trois constructions ont été testées :
1. Somme brute (tirs contestés + déflections)
2. Composite standardisé (z-scores) : tirs contestés + déflections + charges
   provoquées, par minute jouée
3. Le même composite, découpé par groupe de poste (intérieurs vs extérieurs)

Critère de validation retenu : un joueur élu Défenseur de l'Année (DPOY) doit
apparaître dans le haut de classement de sa saison. Testé sur Rudy Gobert
(2023-24), Jaren Jackson Jr. (2022-23) et Giannis Antetokounmpo (2019-20).

Résultat : échec dans les trois cas. Le plus flagrant : JJJ n'apparaît même
pas dans le top 5 des intérieurs sur la saison exacte où il a été élu DPOY.

Cause probable : les stats "hustle" par minute favorisent structurellement les
joueurs à haute activité (ailiers/arrières qui multiplient les contests et
déflections), pas les pivots qui défendent par positionnement et dissuasion
au cercle (ce que ces stats ne captent pas). La métrique propriétaire DBPM
(Basketball-Reference) capterait probablement mieux cet aspect, mais son
scraping est exclu par la politique du projet (voir plus haut).

nba_api expose aussi LeagueDashPtDefend (défense par tracking), mais cet
endpoint s'est révélé peu fiable dans nos tests (JSONDecodeError, 3/3 essais).

Conclusion : aucune métrique défensive individuelle n'a été ajoutée au modèle.
À réévaluer si LeagueDashPtDefend devient exploitable, ou si une autre source
de données fiable apparaît.

## Limites connues du MVP

- La jointure salaire se fait sur le nom du joueur normalisé (`data_sources/base.normalize_name`) —
  de rares homonymes ou orthographes très différentes entre nba_api et le dataset Kaggle peuvent
  ne pas matcher (la ligne reste alors avec Salaire à `NaN`, filtrée automatiquement du scatter).
- Le format de la colonne "saison" du CSV Kaggle est détecté automatiquement (`Season` texte ou
  `Year` numérique) — si le dataset est mis à jour avec un schéma différent, ajuster
  `_resolve_kaggle_columns()` dans `data_sources/nba.py`.
- Le dataset ratin21 s'arrête à la saison qu'il couvre (à vérifier après téléchargement, autour de
  2024-25). Les saisons plus récentes affichent les stats (via nba_api) mais pas le salaire, tant
  que ratin21 n'est pas mis à jour par son auteur.
- Le dataset legacy (1996-97 → 2009-10) n'a pas de colonne PER — comme pour ratin21, seul le PIE
  (nba_api) sert de métrique d'efficacité sur ces saisons.
- Deux trous de couverture connus dans le dataset legacy, 1986-87 et 1989-90 (voir
  `KNOWN_SALARY_DATA_GAPS`) — sans impact aujourd'hui car hors de la plage 1996-97+ effectivement
  utilisée, gardés au cas où la borne basse bouge encore.
