# Tourenplaner – Schritt 2: Solver-Kern

Erfundener Betrieb **„Bäckerei Nordoberpfalz“**: eine Backstube, 14 Filialen, 4 Kantinen, 3 Fahrer.
Keine echten Orte, keine echten Kunden.

## Dateien

| Datei | Aufgabe |
| --- | --- |
| `modell.py` | Datenmodell. Uhrzeiten als Minuten seit Mitternacht. Ausgabe: je Stopp **Ankunft, Beginn, Abfahrt** |
| `fahrzeiten.py` | Fahrzeitmatrix: Luftlinie × 1,3 bei 50 km/h. Später durch OSRM ersetzbar, gleiche Schnittstelle |
| `testdaten.py` | Erzeugt die erfundene Bäckerei, reproduzierbar über den Seed |
| `solver.py` | OR-Tools: wer fährt welche Stopps in welcher Reihenfolge; danach Uhrzeiten vorwärts rechnen |
| `pruefer.py` | Unabhängiger Prüfer: rechnet jeden Plan nach, vertraut dem Solver nicht |
| `main.py` | Kommandozeile: planen, ausgeben, prüfen, optional als JSON speichern |
| `tests/test_planung.py` | 18 Tests: gültige Pläne für 7 Seeds, Prüfer erkennt 6 absichtlich eingebaute Fehler |

## Einrichten und starten

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
python -m pytest -q
```

- `python3 -m venv .venv` – legt eine eigene Python-Umgebung im Ordner `.venv` an. `-m venv` startet das eingebaute Modul `venv`, `.venv` ist der Zielordner.
- `source .venv/bin/activate` – schaltet diese Umgebung in der aktuellen Shell ein; `python` und `pip` zeigen danach auf `.venv`.
- `pip install -r requirements.txt` – installiert die Pakete aus der Datei. `-r` heißt „lies die Liste aus dieser Datei“.
- `python main.py` – plant mit den Standarddaten. Optionen:
  - `--seed 3` andere erfundene Daten (Standard 7)
  - `--fahrer 2` nur zwei Fahrer – zeigt, was offen bleibt
  - `--zeitlimit 5` Rechenzeit des Solvers in Sekunden (Standard 2)
  - `--json plan.json` speichert den Plan zusätzlich als JSON (für Fahrer-Ansicht und Zeitstrahl)
- `python -m pytest -q` – führt alle Tests aus. `-m pytest` startet pytest über den aktiven Python-Interpreter, `-q` (quiet) gibt nur eine Kurzfassung aus.

## Wie das Modell funktioniert

- **Mehrfachtouren:** Jeder Fahrer hat bis zu 3 „Tour-Slots“. Für OR-Tools ist jeder Slot ein eigenes Fahrzeug. Eine Nebenbedingung zwingt Slot k, erst nach Rückkehr von Slot k-1 plus 15 Minuten Beladen zu starten.
- **Erst backen, dann fahren:** Liegt ein Stopp auf einer Tour, fährt die Tour frühestens um Fertigzeit + Ladezeit ab (`IsEqualCstVar` auf die Fahrzeugzuordnung des Stopps).
- **Lieferfenster:** Der Beginn des Entladens muss im Fenster liegen. Früher ankommen und warten ist erlaubt.
- **Offen statt unmöglich:** Jeder Stopp darf gegen eine hohe Strafe ausgelassen werden. So liefert der Solver immer einen Plan und sagt ehrlich, was nicht passt.
- **Uhrzeiten:** OR-Tools liefert nur die Reihenfolge. Die Zeiten rechnet `_zeitplan` vorwärts aus und schiebt die Abfahrt um die Wartezeit am ersten Stopp nach hinten.

## Was die Tests zeigen

- Bei den Seeds 3 und 5 bleibt auch mit 5 s Rechenzeit ein Stopp offen. Die erfundenen Daten sind dort zu eng (weit entfernte Filiale, Fenster bis 05:45). Der Plan ist trotzdem gültig und nennt den Stopp offen.
- Die Rechenzeit zählt: Im Standardfall findet die Suche mit 0,5 s nicht immer alle 18 Stopps, mit 2 s schon.
- Die Startstrategie zählt: `PATH_CHEAPEST_ARC` lieferte hier die besten Startlösungen; Einfüge-Strategien ließen viele Stopps offen.

## Nächste Schritte

1. **Störfall:** Fahrer fällt um Uhrzeit X aus → erledigte Stopps fixieren, Ware im Fahrzeug markieren, Rest neu verteilen (mit/ohne Ersatzfahrer).
2. **OSRM:** `fahrzeiten.py` aus einer OSRM-`/table`-Abfrage füllen; Abbiegestrafen und `approaches=curb`.
3. **Vergleich „Heute gegen Pool“:** feste Touren einlesen und mit demselben Modell nachrechnen.
4. **Oberfläche:** Fahrer-Ansicht und Zeitstrahl lesen `plan.json`.
