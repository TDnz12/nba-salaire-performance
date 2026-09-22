# Méthodologie détaillée

Ce document détaille les choix méthodologiques et leurs itérations, pour qui veut le détail complet au-delà du README.

## Mode "Toutes les saisons"

En plus du sélecteur saison par saison, le dashboard propose une vue combinée ("Toutes les
saisons (1996-97 → 2025-26)" dans le sélecteur) qui charge et concatène l'intégralité de
`sport.seasons` — chaque joueur y apparaît comme un point distinct par saison jouée.

Une saison dont le salaire est indisponible n'empêche pas d'afficher les autres : elle apparaît
simplement avec cette colonne vide plutôt que de faire échouer tout le mode combiné.

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
`nba.py`) : si la logique de calcul change (nouvelle colonne, nouveau calcul dérivé...), un
cache écrit sous une version différente est automatiquement ignoré et recalculé, sans besoin de
cliquer sur "Rafraîchir" à la main.

## Métrique défensive individuelle (piste abandonnée)

Une tentative a été faite pour intégrer une métrique de "défense" individuelle
en complément des métriques offensives (PIE, impact hors scoring), basée sur
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

Conclusion : aucune métrique défensive individuelle n'a été ajoutée au dashboard.
À réévaluer si LeagueDashPtDefend devient exploitable, ou si une autre source
de données fiable apparaît.
