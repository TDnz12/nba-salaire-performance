# Méthodologie détaillée

Ce document détaille les choix méthodologiques et leurs itérations, pour qui veut le détail complet au-delà du README.

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
de données" du README), aucune variable hors box-score officiel n'a été envisagée comme 4ᵉ piste.
Conséquence pratique pour la lecture du dashboard : un scoreur pur à très haut volume peut
apparaître "surpayé" (`value_added` très négatif) au-delà de ce que sa valeur réelle justifierait
— un avertissement en ce sens est affiché dans l'UI (expander méthodologie).

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
  n'aurait pas de sens vu la hausse du plafond salarial (voir section normalisation du README). En
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
scraping est exclu par la politique du projet (voir README).

nba_api expose aussi LeagueDashPtDefend (défense par tracking), mais cet
endpoint s'est révélé peu fiable dans nos tests (JSONDecodeError, 3/3 essais).

Conclusion : aucune métrique défensive individuelle n'a été ajoutée au modèle.
À réévaluer si LeagueDashPtDefend devient exploitable, ou si une autre source
de données fiable apparaît.
