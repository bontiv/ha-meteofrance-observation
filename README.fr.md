# Météo-France Observation

Intégration Home Assistant qui lit en temps réel les **mesures des stations au sol de Météo-France**. Chaque station publie une observation toutes les 6 minutes : température, humidité, pression, vent, précipitations.

Elle a été conçue pour fournir la **température extérieure** de [Versatile Thermostat](https://github.com/jmcollin78/versatile_thermostat). Une mesure réelle et fréquente améliore la régulation, surtout avec l'Auto-TPI.

> [!NOTE]
> L'intégration native `meteo_france` donne des prévisions et des valeurs de modèle sur un point de grille. Celle-ci donne la valeur **mesurée** par la station que vous choisissez.

## Points forts

- Identifiants Météo-France stockés dans les **Identifiants de l'application** de Home Assistant (fonction native).
- Jetons renouvelés automatiquement toutes les heures : plus de clé API qui expire sans prévenir.
- Recherche de la station **autour d'un point sur la carte**, **par département** ou **par identifiant**.
- Aucune ligne de YAML à écrire.

## Installation

[![Ouvrir le dépôt dans HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bontiv&repository=ha-meteofrance-observation&category=integration)

1. Dans HACS, ajoutez ce dépôt comme dépôt personnalisé de type **Intégration** (ou utilisez le bouton ci-dessus).
2. Installez **Météo-France Observation**, puis redémarrez Home Assistant.

## 1. Créer l'accès à l'API Météo-France

L'API est gratuite.

1. Créez un compte sur le [portail API Météo-France](https://portail-api.meteofrance.fr) et connectez-vous.
2. Ouvrez l'API [Données Publiques Observation](https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesObservation) et souscrivez-y.
3. Dans **Mes API**, cliquez sur **Générer token** pour cette API et choisissez **OAuth2**.
4. En bas de page, l'exemple `curl` contient `Authorization: Basic` suivi d'une longue valeur. Copiez cette valeur.

> [!TIP]
> Cette valeur est `APPLICATION_ID:APPLICATION_SECRET` encodé en Base64. L'intégration la décode et enregistre l'identifiant et le secret dans les **Identifiants de l'application** de Home Assistant.

## 2. Ajouter la station dans Home Assistant

[![Ajouter l'intégration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=meteofrance_observation)

1. **Paramètres > Appareils et services > Ajouter une intégration > Météo-France Observation**.
2. Collez la valeur copiée après `Authorization: Basic` (coller l'en-tête complet fonctionne aussi). Le rappel des étapes ci-dessus s'affiche dans cette fenêtre. Si des identifiants sont déjà enregistrés, Home Assistant propose de les réutiliser.
3. Choisissez comment trouver la station :
   - **Autour d'un point sur la carte** : le repère est placé sur votre domicile. Les 20 stations les plus proches sont proposées avec leur distance et leur altitude.
   - **Par département** : toutes les stations du département, triées par nom.
   - **Je connais l'identifiant** : 8 chiffres, par exemple `75110001` pour Paris-Lariboisière.
4. Choisissez la station. L'intégration vérifie qu'elle publie bien des observations toutes les 6 minutes.

Préférez une station proche et à une altitude semblable à celle de votre domicile. Pour suivre plusieurs stations, ajoutez l'intégration plusieurs fois : les mêmes identifiants servent pour toutes.

## 3. Utiliser avec Versatile Thermostat

Dans la **configuration centrale** de Versatile Thermostat (ou dans chaque VTherm), sélectionnez le capteur `sensor.<station>_temperature` comme **capteur de température extérieure**.

## Capteurs

| Capteur | Unité | Activé par défaut |
| --- | --- | --- |
| Température | °C | oui |
| Humidité | % | oui |
| Point de rosée | °C | non |
| Pression atmosphérique | hPa | non |
| Pression au niveau de la mer | hPa | non |
| Vitesse du vent | m/s | non |
| Direction du vent | ° | non |
| Rafale de vent (sur 10 min) | m/s | non |
| Précipitations (sur 6 min) | mm | non |

Chaque capteur indique l'heure de l'observation (`observation_time`) et la position de la station. Une valeur que la station n'a pas mesurée rend le capteur **indisponible** au lieu de renvoyer une valeur fausse.

## Options

**Intervalle de mise à jour** : 10 minutes par défaut, 6 minutes minimum. Les stations ne publient pas plus souvent.

## Dépannage

- **« L'application n'est pas abonnée à l'API »** : souscrivez à *Données Publiques Observation* sur le portail, puis validez la réauthentification proposée par Home Assistant.
- **« Cette station ne publie pas d'observation toutes les 6 minutes »** : certaines stations du réseau ne transmettent pas en temps réel. Choisissez-en une autre.
- **Identifiants modifiés ou supprimés** : mettez-les à jour dans **Paramètres > Appareils et services > menu ⋮ > Identifiants de l'application**.

## Migrer depuis le capteur REST

Si vous utilisiez la configuration `rest:` du [guide de la discussion VTherm #1552](https://github.com/jmcollin78/versatile_thermostat/discussions/1552) :

1. Ajoutez la station avec cette intégration.
2. Dans Versatile Thermostat, remplacez l'ancien capteur par le nouveau.
3. Supprimez le bloc `rest:` de `configuration.yaml` et redémarrez.

## Données

Les données proviennent de l'API publique de Météo-France, qui ne conserve que les 24 dernières heures. Ce projet est indépendant et n'est pas affilié à Météo-France.
