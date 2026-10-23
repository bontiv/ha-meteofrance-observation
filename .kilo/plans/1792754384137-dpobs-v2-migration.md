# Migration DPObs v2 (avec repli v1) + notes de documentation

## Contexte

Fil HACF du 23/10/2026 ([forum.hacf.fr/t/meteo-france-observation-api-version/84902](https://forum.hacf.fr/t/meteo-france-observation-api-version/84902)) :

1. **Abonnement vv1 vs vv2** : un nouvel utilisateur a souscrit à la **vv2** sur le portail et l'intégration refusait la clé (403). Il a dû souscrire à la **vv1**. Cause vérifiée : la page du portail liée dans le README (`/web/fr/api/DonneesPubliquesObservation`) affiche désormais **vv2** par défaut, et un abonnement n'est valable que pour une version. L'intégration appelle `.../public/DPObs/v1/...` (`const.py:14`).
2. **Humidité / vent indisponibles** : beaucoup de stations n'ont pas ces capteurs, l'API renvoie `null`, le capteur passe `indisponible` (comportement voulu, déjà documenté).

Faits critiques vérifiés (annonce Météo-France du 28/05/2026, mise à jour 10/06/2026, [Confluence](https://confluence-meteofrance.atlassian.net/wiki/spaces/OpenDataMeteoFrance/pages/1688633417)) :

- **v2 déployée le 8 juin 2026** ; v1 et v2 cohabitent temporairement.
- **Depuis le 16 juin 2026, les paramètres de rafales v1 (`fxi`, `dxi`, `fxi10`, `dxi10`) ne sont plus alimentés** → le capteur *Rafale de vent* (`fxi10`, `sensor.py:154`) est indisponible pour tous depuis juin.
- **v1 sera arrêtée le 1er décembre 2026** (~5 semaines). Sans migration, l'intégration cesse de fonctionner pour tous.
- En v2, pour `/station/infrahoraire-6m` : seuls renommages `fxi10` → `raf10` et `dxi10` → `ddraf10`. Tous les autres champs lus par l'intégration (`t`, `td`, `u`, `dd`, `ff`, `rr_per`, `pres`, `pmer`, `validity_time`) sont inchangés, de même que les chemins (`/liste-stations`, `/station/infrahoraire-6m`).

## Décisions

- **Migrer vers v2 avec repli v1** : chaque requête interroge v2 ; sur 403, elle retente sur v1. Les abonnés vv1 continuent de fonctionner jusqu'au 1er décembre 2026 ; les abonnés vv2 (défaut du portail, cas des nouveaux utilisateurs) fonctionnent immédiatement.
- **2ᵉ retour du forum** : note de documentation uniquement (Dépannage des README), pas de changement de code.
- Pas de changement d'`unique_id` des entités : le renommage `fxi10`/`raf10` est interne au `value_fn`, aucune migration d'entités.

## Tâches

### 1. `custom_components/meteofrance_observation/const.py`

Remplacer `API_BASE_URL` par deux constantes :

- `API_BASE_URL_V2: Final = "https://public-api.meteofrance.fr/public/DPObs/v2"`
- `API_BASE_URL_V1: Final = "https://public-api.meteofrance.fr/public/DPObs/v1"`

`API_PAGE_URL` et `PORTAL_URL` restent inchangés (la page pointe par défaut sur vv2, conforme au nouveau défaut).

### 2. `custom_components/meteofrance_observation/api.py` — repli v1

Restructurer `MeteoFranceObsClient._async_get` :

- Extraire la logique actuelle (boucle 401 → rafraîchissement du token + retry une fois, puis mapping 200/401/403/204-400-404/autre) dans un helper `_async_get_from(base_url, path, params)`.
- `_async_get` essaie v2 puis v1 avec la sémantique :
  - v2 **200** → retour (cas nominal, 1 seule requête).
  - v2 **403** (`MeteoFranceNotSubscribedError`) → tentative v1.
  - v1 **200** → retour (abonné vv1).
  - v1 **403** → lever `MeteoFranceNotSubscribedError` (abonné à aucune version).
  - v1 **autre échec** (NoData, connection…) après un 403 v2 → lever le `MeteoFranceNotSubscribedError` du 403 v2 en journalisant l'échec v1. Justification : le message actionnable est « souscrivez à l'API » (v1 étant condamnée) ; évite notamment le message trompeur « cette station ne publie pas d'observation » quand v1 sera coupée le 1er décembre.
  - **401 ne déclenche jamais le repli** (uniquement le rafraîchissement de token existant) ; seul 403 bascule de version.
- `async_get_stations` et `async_get_observation` inchangés (elles passent par `_async_get`).

### 3. `custom_components/meteofrance_observation/sensor.py` — rafale

- Ajouter un helper `_number_first(*keys)` : première valeur non `None` parmi les clés.
- Rafale de vent : `value_fn=_number("fxi10")` → `value_fn=_number_first("raf10", "fxi10")` (v2 d'abord, v1 en repli).
- Tous les autres capteurs inchangés (noms de champs identiques en v2).

### 4. Tests — `tests/conftest.py`, `tests/test_sensor.py`, `tests/test_config_flow.py`

- conftest : importer `API_BASE_URL_V2` / `API_BASE_URL_V1` ; `STATIONS_URL`/`OBSERVATION_URL` deviennent les URLs **v2** ; ajouter les URLs v1. Fixture `OBSERVATION` : remplacer `"fxi10": 5.1` par `"raf10": 5.1`.
- Ajouter un scénario vv1 (ex. paramètre de `mock_api` ou `mock_api_v1`) : URLs v2 → 403, URLs v1 → 200 avec une observation contenant `fxi10`.
- **Attention** : les tests existants qui mockent 403 sur l'URL v2 doivent aussi mocker 403 sur l'URL v1, sinon le repli déclenche un appel non mocké (échec `AiohttpClientMocker`) : `test_new_credentials_errors` (cas `200, 403`), `test_credentials_errors` (cas `200, 403`), `test_reauth`.
- `test_revoked_token_is_renewed` (401) : inchangé — 401 ne bascule pas de version, l'assertion `["GET", "POST", "GET"]` reste valide.
- Nouveaux tests :
  - repli v1 : v2 403 + v1 200 (`fxi10`) → setup OK, la rafale lit `fxi10`, les autres capteurs fonctionnent.
  - rafale en v2 : la valeur vient de `raf10` (activer l'entité ou vérifier via le registre / l'état).
  - v2 403 + v1 403 → `not_subscribed`.

### 5. `strings.json` + `translations/{en,fr,de}.json`

- `config.step.credentials.description` (étape 2) : préciser la souscription à la **version 2**.
- `config.error.not_subscribed`, `config.abort.not_subscribed`, `exceptions.not_subscribed` : mentionner la version 2.
- Harmoniser les trois traductions.

### 6. README `README.md`, `README.fr.md`, `README.de.md`

- Section « 1. Créer l'accès à l'API », étape 2 : souscrire à *Données Publiques Observation* **version 2** (page par défaut du portail) ; préciser que la version 1 fonctionne aussi mais sera retirée par Météo-France le **1er décembre 2026**.
- Dépannage :
  - Compléter « L'application n'est pas abonnée à l'API » : souscrire à la **v2** (ou v1 jusqu'au 1er décembre 2026), puis réauthentification.
  - **Nouvelle entrée** (2ᵉ retour du forum) : « Humidité, vent ou un autre capteur est indisponible » — beaucoup de stations n'ont pas ce capteur, l'API ne renvoie pas de valeur et le capteur reste indisponible ; choisir une autre station si la mesure est nécessaire.
- Pas de mention des noms de champs internes (`raf10`) dans le README.

### 7. Validation locale

- `ruff check .` (config pyproject : E, F, W, I, UP, B ; ligne ≤ 100).
- `python -m pytest` (tests complets ; CI exécute aussi hassfest + HACS via `validate.yml`).
- Optionnel mais recommandé avant la release : vérifier une fois l'API réelle avec un jeton vv2 (p. ex. `curl https://public-api.meteofrance.fr/public/DPObs/v2/station/infrahoraire-6m?id_station=75110001&format=json`) pour confirmer le champ `raf10` ; l'annonce Confluence fait autorité à défaut.

### 8. Release v0.3.0

- Déclencher le workflow **Release** (`workflow_dispatch`, version `0.3.0`) : il met à jour `manifest.json`, taggue, construit le zip HACS et crée la release GitHub. Ne pas modifier `manifest.json` à la main.
- Notes de release : support v2 avec repli v1 ; arrêt v1 par Météo-France le 1er décembre 2026 (inviter les abonnés vv1 à souscrire la v2) ; correction de la rafale de vent (paramètre v1 non alimenté depuis le 16 juin 2026) ; note doc sur les capteurs absents selon la station.
- Hors dépôt (action utilisateur) : répondre sur le fil HACF une fois la version publiée.

## Risques / points ouverts

- **Comportement exact de v1 après le 1er décembre 2026** (404, 410, 403…) inconnu ; la sémantique du repli (tout échec v1 après 403 v2 → `not_subscribed`) couvre tous les cas avec un message actionnable.
- **Abonnés vv1** : la rafale de vent reste indisponible jusqu'à leur souscription v2 (`fxi10` n'est plus alimentée depuis juin) ; les autres capteurs fonctionnent via le repli.
- **Vérification du champ `raf10`** : fondée sur l'annonce officielle ; à confirmer par un appel réel si possible (voir tâche 7).
- La liste des stations et le parseur `stations.py` sont identiques entre v1 et v2 (chemins inchangés) ; aucun impact.
