# ALADIN37 – Night-Watcher Contract v0.3 (FREEZE CANDIDATE)
Status: EINGEFROREN — Provenienz-Commit 6f26d7c933cc3512a1ae4d09488478148fd61901 (2026-09-09)
Basis: Contract v0.1 + Bootstrap Addendum v1.0 (ACCEPTED) + v0.2 Merge (Scope- und
file_id-Erweiterung von Jens bestätigt)

> **Merge-Prinzip:** Nur Änderungen, die durch Addendum v1.0 gefordert sind oder einen
> erkennbaren Konsistenzkonflikt auflösen, wurden vorgenommen. Alles andere ist
> wortgleich aus Contract v0.1 übernommen. Jede Änderung ist markiert:
> `[ADDED]` / `[MODIFIED]` / `[REMOVED]` / `[UNCHANGED]`.
>
> **Reihenfolge bis hierher:** Contract-Semantik → Konfliktauflösung → Bootstrap-Regeln
> → Merge → Validierung (dieser Schritt) → Freeze → Git-Commit als Provenienz. Der
> Commit-Hash wird nicht vorab erfunden, sondern erst nach dem finalen Contract-Stand
> als unveränderliche Provenienzreferenz eingetragen.

---

## Changelog (Übersicht)

| # | Abschnitt | Art | Grund |
|---|-----------|-----|-------|
| 1 | 1 Scope | **MODIFIED** — ✅ von Jens bestätigt | Konsistenzkonflikt: Addendum setzt lokale/Git-Quelle voraus, Scope kannte bisher nur Drive |
| 2 | 2.2 file_registry.jsonl | **MODIFIED** — ✅ von Jens bestätigt | `file_id` war Drive-spezifisch definiert, muss auch lokale/Git-Identifier zulassen; `commit_id` bleibt optional, keine Pflicht für Nicht-Git-Lokalquellen |
| 3 | 2.4 (neu) | **ADDED** | Definiert `ALADIN37_STATE.json` als Knowledge-State, getrennt von `scan_state.json` |
| 4 | 4 Evidence Rule | **ADDED** | Lokale/Git-Evidence-Regel aus Addendum §4 ergänzt |
| 5 | 7 Freigabe-/Freeze-Gate | **ADDED** | Bootstrap-State-Prüfpunkt + korrigierte Freeze-Reihenfolge |
| 6 | 0, 3, 5, 6 | **UNCHANGED** | Kein Bezug zu Addendum, kein Konflikt |

---

## 0. Leitprinzip `[UNCHANGED]`

Der Night-Watcher muss nicht zuerst intelligent werden. Er muss zuerst deterministisch beobachten können.

State ist nicht Knowledge. Knowledge ist nicht Source. Report ist nicht Action.

```
SOURCES ──────────────► OBSERVATION
                           │
                           ▼
                        ANALYSIS
                           │
                           ▼
OUTBOX ◄──────────────── REPORT
STATE  ◄──────────────── STATE
```
OUTBOX ─X→ SOURCES — diese Kante existiert nicht. Niemals.

---

## 1. Scope `[MODIFIED — bitte explizit bestätigen]`

Beobachtet werden ausschließlich die explizit freigegebenen Quellen unter SOURCES.
SOURCES ist read-only für den Night-Watcher — kein Schreiben, kein Verschieben, kein
Löschen, kein Umbenennen — **unabhängig vom Quelltyp**.

Zwei zulässige Quelltypen `[ADDED]`:

| Quelltyp | Beschreibung | Identifikationsschema |
|----------|-------------|------------------------|
| Drive-Scope | Google-Drive-Ordner (ursprünglicher v0.1-Fall) | Drive-`file_id` |
| Lokal/Git-Scope (Bootstrap) | Lokales Repository/Verzeichnis | Repository-relativer Pfad + Commit/Blob-Identifier, siehe Abschnitt 2.4 |

Ordner/Pfade außerhalb des definierten Scope werden nicht gescannt, auch nicht "zur
Sicherheit" oder "weil sie verlinkt sind". Scope-Änderungen erfordern eine explizite,
manuelle Änderung dieses Contracts — nicht eine Entscheidung des Agenten zur Laufzeit.
Ein einzelner Night-Watcher-Lauf operiert immer nur in genau einem Scope-Typ zur Zeit;
Drive-Scope und Lokal/Git-Scope werden nicht in einem Lauf vermischt.

Offen zu befüllen (vor Inbetriebnahme):
- Liste der exakten Drive-Ordner-IDs/Pfade unter SOURCES (Drive-Scope)
- Lokaler Repository-Pfad unter SOURCES (Lokal/Git-Scope, Bootstrap)

---

## 2. State Schema `[teilweise MODIFIED/ADDED, siehe unten]`

Der State wird in **vier** strikt getrennte Dateien aufgeteilt (bisher drei). Keine
Datei übernimmt die Aufgabe einer anderen.

### 2.1 STATE/scan_state.json — technischer Laufzustand `[UNCHANGED]`
**Runtime Truth — ausschließlich diese Datei ist authoritative für den operativen
Scan-Zustand.** Keine andere State-Datei (insbesondere nicht `ALADIN37_STATE.json`,
siehe 2.4) darf diesen Zustand darstellen oder ersetzen.

```json
{
  "schema_version": "1.0",
  "last_scan_utc": "2026-09-06T23:00:00Z",
  "run_id": "uuid",
  "scope": "SOURCES",
  "status": "completed"
}
```

### 2.2 STATE/file_registry.jsonl — Beobachtungsebene `[MODIFIED]`
Semantik unverändert: aktueller Beobachtungsstand, ein Datensatz pro `file_id`, bei
Änderung per Key aktualisiert. Kein Append-only-Log. Historie ergibt sich ausschließlich
aus den Nightly-Reports in OUTBOX bzw. einem separat definierten Audit-Log.

| Feld | Bedeutung |
|------|-----------|
| `file_id` | **[MODIFIED]** generischer, quellentypabhängiger Identifier: repräsentiert die Drive-`file_id` im Drive-Scope, den definierten lokalen Identifier/Pfad im Lokal/Git-Scope |
| `name` | Dateiname |
| `path` | Pfad relativ zu SOURCES |
| `mime_type` | MIME-Typ |
| `modified_time` | letzte Änderung laut Quelle |
| `size` | Dateigröße in Bytes |
| `sha256` | Inhalts-Hash |
| `commit_id` | **[ADDED]** optional, ausschließlich für Git-Kontext innerhalb des Lokal/Git-Scope; **keine Pflicht** für reine Nicht-Git-Lokalquellen |
| `last_seen_run` | run_id des letzten Scans, in dem die Datei existierte |
| `last_analyzed_run` | run_id der letzten inhaltlichen Analyse |

### 2.3 STATE/watcher_policy.md — unveränderliche Verhaltensregel `[UNCHANGED]`
```
READ:
  SOURCES

WRITE:
  STATE/scan_state.json
  STATE/file_registry.jsonl
  OUTBOX/reports/<date>-nightly.md   # exakter Pfad, kein allgemeiner OUTBOX-Zugriff

FORBIDDEN:
  SOURCES modification
  deletion
  trash
  financial action
  external action
  self-modification
```
Diese Datei wird vom Agenten niemals verändert. Änderungen erfolgen ausschließlich
manuell durch Jens.

### 2.4 BOOTSTRAP/ALADIN37_STATE.json — Knowledge-State `[ADDED]`
Gilt ausschließlich für den Bootstrap-Fall (Erstinitialisierung, insbesondere
Lokal/Git-Scope). Diese Datei ist **kein** Ersatz und keine zweite Fassung von
`scan_state.json`. Sie beschreibt den initialen, projektbezogenen Knowledge-Stand,
nicht den operativen Laufzustand.

```json
{
  "schema_version": "0.1.0",
  "state_role": "PROJECT_KNOWLEDGE_STATE",
  "status": "UNINITIALIZED",
  "last_baseline_scan": null,
  "baseline_established": false,
  "file_index": []
}
```

Verbindliche Regeln:
- `last_baseline_scan` darf bei Erstinitialisierung **niemals** einen zukünftigen oder
  geschätzten Zeitpunkt enthalten. Zulässig ist ausschließlich `null` mit
  `"status": "UNINITIALIZED"`, oder der tatsächlich belegte Zeitpunkt eines real
  durchgeführten Scans.
- `file_index: []` bedeutet: noch kein lokal etablierter Dateikatalog. Wird nicht
  künstlich mit Drive-Dateien oder alten Reports vorbefüllt.
- Empfohlene Ordnerstruktur:
  ```
  aladin-move37/
  └── ALADIN37_NightWatcher/
      ├── bootstrap/
      │   └── ALADIN37_NightWatcher_Bootstrap.md
      ├── state/
      │   ├── ALADIN37_STATE.json      # Knowledge-State (dieser Abschnitt)
      │   └── scan_state.json          # authoritative Laufzeitquelle (Abschnitt 2.1)
      └── reports/
          └── delta_report_<date>.md   # append-only Evidenz
  ```
- Ein Wechsel dieser Rollenverteilung (z. B. Zusammenführung zu einem einzigen
  kanonischen State) ist nur über eine explizite neue Contract-Änderung zulässig,
  niemals stillschweigend.

---

## 3. Detection Rule `[UNCHANGED]`

Klassifikation ausschließlich über genau vier Vergleichsgrößen zwischen
`file_registry.jsonl` (vorheriger Lauf) und dem aktuellen Scan:

1. Existenz im vorherigen Snapshot
2. Existenz im aktuellen Scan
3. `sha256` (Inhaltsbeweis)
4. `modified_time` (Zusatzmetadatum)

| Zustand | Bedingung |
|---------|-----------|
| NEW | `file_id` nicht in vorherigem Registry-Snapshot vorhanden |
| MODIFIED | `file_id` in beiden Snapshots vorhanden, `sha256` weicht ab |
| UNCHANGED | `file_id` in beiden Snapshots vorhanden, `sha256` identisch |
| MISSING | `file_id` war in vorherigem Snapshot vorhanden, fehlt im aktuellen Scan |

`sha256` ist das maßgebliche Kriterium für MODIFIED — nicht `modified_time`. Kein
Zustand darf aus Heuristik, Modell-Interpretation oder "Plausibilität" abgeleitet
werden — ausschließlich aus den vier oben genannten Datenvergleichen.

---

## 4. Evidence Rule `[ADDED: Lokal/Git-Ergänzung]`

Was der Agent in den Nightly Report schreiben darf (unverändert aus v0.1):
- Aussagen über Delta-Fakten aus Abschnitt 3, belegt durch `file_registry.jsonl`.
- Direkte, referenzierbare Beobachtungen aus dem Dateiinhalt selbst, mit Verweis auf
  `file_id`/`path`.

Was der Agent nicht schreiben darf (unverändert aus v0.1):
- Eigene Nightly-Reports oder sonstige OUTBOX-Artefakte als Beleg für eine inhaltliche
  Veränderung heranziehen. Ein Lauf darf niemals seinen eigenen erfolgreichen Vorlauf
  als Erkenntnis über ALADIN37 selbst interpretieren.
- Spekulative Schlussfolgerungen, Trendinterpretationen oder Handlungsempfehlungen, die
  über O → H → E → MT hinausgehen.
- Finanzielle, rechtliche oder operative Handlungsempfehlungen mit
  Verbindlichkeitscharakter.

**`[ADDED]` Evidence-Anforderung für Lokal/Git-Scope:**
```
Evidence requires:
- stable local file identifier/path,
- modification timestamp,
- content hash where available,
- short quote for substantive claims.

For Git additionally:
- repository-relative path
- commit/blob identifier when available
```
Diese Fassung ersetzt für den Lokal/Git-Scope die implizite Drive-`file_id`-Erwartung
aus v0.1, ohne den Drive-Scope selbst zu verändern.

---

## 5. Write Boundary `[UNCHANGED]`

Der Agent darf ausschließlich erzeugen oder verändern:
- `STATE/scan_state.json`
- `STATE/file_registry.jsonl`
- `OUTBOX/reports/<date>-nightly.md` (neu, niemals überschreiben bestehender Reports)

Der Agent darf unter keinen Umständen:
- irgendetwas unter SOURCES verändern, verschieben, umbenennen oder löschen
- `STATE/watcher_policy.md` verändern
- Dateien im Papierkorb ablegen oder endgültig löschen
- externe Aktionen auslösen
- sich selbst modifizieren

---

## 6. Freigabe-Gate `[UNCHANGED]`

Jeder Nightly Report ist ein Vorschlag, keine Aktion. Der Report landet in OUTBOX und
wartet auf menschliche Freigabe. Ohne explizite Freigabe durch Jens erfolgt keine
Weiterverarbeitung, keine Übernahme in andere ALADIN37-Systeme und keine Kommunikation
nach außen.

---

## 7. Status dieses Contracts `[ADDED: Bootstrap-Prüfpunkt + korrigierte Reihenfolge]`

- [ ] Scope final befüllt (Abschnitt 1, inkl. Lokal/Git-Pfad falls Bootstrap) — Scope-Typen selbst ✅ von Jens bestätigt, konkrete Pfade/IDs noch offen
- [x] State Schema von Jens geprüft (inkl. `[ADDED]` Abschnitt 2.4)
- [x] Detection Rule von Jens geprüft
- [x] Evidence Rule von Jens geprüft (inkl. `[ADDED]` Lokal/Git-Ergänzung)
- [x] Write Boundary von Jens geprüft
- [x] **`[ADDED]`** Bootstrap-State geprüft: `ALADIN37_STATE.json` enthält
      `"status": "UNINITIALIZED"`, `"last_baseline_scan": null`, `"file_index": []`
- [x] Contract eingefroren (Datum: **2026-09-09**, Git-Commit: `6f26d7c933cc3512a1ae4d09488478148fd61901`)
      — Provenienz-Hash nachgetragen. Contract ist formal EINGEFROREN.

**`[ADDED]` Verbindliche Reihenfolge nach Freeze:**
```
CONTRACT MERGE / VALIDATION
        ↓
      FREEZE
        ↓
  INITIAL BASELINE   (regulärer Lauf, schreibt ausschließlich scan_state.json)
        ↓
NightWatcher DELTA RUNS
```
Freeze friert Architektur und Bootstrap-Semantik ein. Die Initial Baseline ist danach
ein regulärer operativer Lauf, kein Teil der eingefrorenen Spezifikation — sie erzeugt
keine rückwirkende Neubewertung, insbesondere nicht von `delta_report_2026-09-08`.

Erst nach vollständigem Freeze wird der Automation-Prompt (z. B. für Grok) aus diesem
Contract mechanisch abgeleitet.

---

## Freeze-Readiness-Check (Zusammenfassung)

| Prüfpunkt | Status |
|-----------|--------|
| Future-Timestamp-Problem | ✅ behoben (Abschnitt 2.4) |
| Runtime Truth eindeutig | ✅ `scan_state.json` (2.1) |
| Knowledge-State getrennt | ✅ `ALADIN37_STATE.json` (2.4) |
| `file_index: []` korrekt interpretiert | ✅ (2.4) |
| Evidence Rule lokal/Git | ✅ ergänzt (4) |
| Scope-Konflikt Drive/Lokal | ✅ **bestätigt** (1) |
| `file_registry.jsonl` Generalisierung (`file_id`, `commit_id` optional) | ✅ **bestätigt** (2.2) |
| Freeze-Reihenfolge | ✅ korrigiert (7) |
| Bestehende Reports (`delta_report_2026-09-08`) | ✅ unverändert |
| Provenienz-Hash eingetragen | ✅ 6f26d7c933cc3512a1ae4d09488478148fd61901 |

**Status:** EINGEFROREN. Nächster isolierter Schritt: Gate 2 — expliziten Scope befüllen.
