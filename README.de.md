# Météo-France Observation

Home-Assistant-Integration, die die **Messwerte der Bodenstationen von Météo-France** in Echtzeit liest. Jede Station veröffentlicht alle 6 Minuten eine Beobachtung: Temperatur, Luftfeuchtigkeit, Luftdruck, Wind und Niederschlag.

Sie wurde entwickelt, um die **Außentemperatur** für [Versatile Thermostat](https://github.com/jmcollin78/versatile_thermostat) zu liefern. Ein echter, häufiger Messwert verbessert die Regelung, besonders mit Auto-TPI.

Météo-France deckt das französische Mutterland und die französischen Überseegebiete ab.

> [!NOTE]
> Die eingebaute Integration `meteo_france` liefert Vorhersagen und Modellwerte für einen Gitterpunkt. Diese Integration liefert den von der gewählten Station **gemessenen** Wert.

## Highlights

- Die Météo-France-Zugangsdaten werden in den eingebauten **Anwendungsanmeldeinformationen** von Home Assistant gespeichert.
- Tokens werden stündlich automatisch erneuert: Kein API-Schlüssel läuft mehr unbemerkt ab.
- Station suchen **um einen Punkt auf der Karte**, **nach Département** oder **per ID**.
- Kein YAML nötig.

## Installation

[![Repository in HACS öffnen.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bontiv&repository=ha-meteofrance-observation&category=integration)

1. Füge dieses Repository in HACS als benutzerdefiniertes Repository vom Typ **Integration** hinzu (oder nutze den Button oben).
2. Installiere **Météo-France Observation** und starte Home Assistant neu.

## 1. Zugang zur Météo-France-API einrichten

Die API ist kostenlos.

1. Erstelle ein Konto im [Météo-France API-Portal](https://portail-api.meteofrance.fr) und melde dich an.
2. Öffne die API [Données Publiques Observation](https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesObservation) und abonniere sie.
3. Klicke unter **Mes API** bei dieser API auf **Générer token** und wähle **OAuth2**.
4. Unten auf der Seite enthält das `curl`-Beispiel `Authorization: Basic APPLICATION_ID`. Kopiere diese **Application ID**.

> [!TIP]
> Die Application ID ist der *Consumer Key* und das *Consumer Secret* deiner Anwendung, gemeinsam kodiert. Zeigt dir das Portal diese beiden Werte, kannst du stattdessen diese eingeben.

## 2. Station in Home Assistant hinzufügen

[![Integration hinzufügen.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=meteofrance_observation)

1. **Einstellungen > Geräte & Dienste > Integration hinzufügen > Météo-France Observation**.
2. Home Assistant fragt zuerst nach den Anwendungszugangsdaten. Füge die **Application ID** in beide Felder ein, **Client-ID** und **Client-Secret**. Die Schritte oben werden in diesem Dialog angezeigt.
3. Wähle, wie die Station gefunden werden soll:
   - **Um einen Punkt auf der Karte**: Die Markierung steht auf deinem Zuhause. Die 20 nächstgelegenen Stationen werden mit Entfernung und Höhe vorgeschlagen.
   - **Nach Département**: alle Stationen des Départements, nach Namen sortiert.
   - **Ich kenne die Stations-ID**: 8 Ziffern, zum Beispiel `75110001` für Paris-Lariboisière.
4. Wähle die Station. Die Integration prüft, ob sie alle 6 Minuten Beobachtungen veröffentlicht.

Wähle eine nahe Station auf ähnlicher Höhe wie dein Zuhause. Für mehrere Stationen füge die Integration mehrmals hinzu: Dieselben Zugangsdaten gelten für alle.

## 3. Mit Versatile Thermostat verwenden

Wähle in der **zentralen Konfiguration** von Versatile Thermostat (oder in jedem VTherm) den Sensor `sensor.<station>_temperature` als **Außentemperatursensor**.

## Sensoren

| Sensor | Einheit | Standardmäßig aktiviert |
| --- | --- | --- |
| Temperatur | °C | ja |
| Luftfeuchtigkeit | % | ja |
| Taupunkt | °C | nein |
| Luftdruck | hPa | nein |
| Luftdruck auf Meereshöhe | hPa | nein |
| Windgeschwindigkeit | m/s | nein |
| Windrichtung | ° | nein |
| Windböe (über 10 min) | m/s | nein |
| Niederschlag (über 6 min) | mm | nein |

Jeder Sensor zeigt die Beobachtungszeit (`observation_time`) und den Standort der Station. Ein von der Station nicht gemessener Wert macht den Sensor **nicht verfügbar**, statt einen falschen Wert zu liefern.

## Optionen

**Aktualisierungsintervall**: standardmäßig 10 Minuten, mindestens 6 Minuten. Die Stationen veröffentlichen nicht häufiger.

## Fehlerbehebung

- **„Die Anwendung hat die API nicht abonniert“**: Abonniere *Données Publiques Observation* im Portal und bestätige dann die von Home Assistant angebotene erneute Authentifizierung.
- **„Diese Station veröffentlicht keine 6-Minuten-Beobachtung“**: Manche Stationen des Netzes melden nicht in Echtzeit. Wähle eine andere.
- **Geänderte oder gelöschte Zugangsdaten**: Aktualisiere sie unter **Einstellungen > Geräte & Dienste > Drei-Punkte-Menü > Anwendungsanmeldeinformationen**.

## Umstieg vom REST-Sensor

Falls du die `rest:`-Konfiguration aus der [Anleitung in der VTherm-Diskussion #1552](https://github.com/jmcollin78/versatile_thermostat/discussions/1552) genutzt hast:

1. Füge die Station mit dieser Integration hinzu.
2. Ersetze in Versatile Thermostat den alten Sensor durch den neuen.
3. Entferne den `rest:`-Block aus `configuration.yaml` und starte neu.

## Daten

Die Daten stammen aus der öffentlichen API von Météo-France, die nur die letzten 24 Stunden vorhält. Dieses Projekt ist unabhängig und nicht mit Météo-France verbunden.
