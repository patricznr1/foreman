# TimescaleDB-Tuning der `readings`-Hypertable für insert-heavy Sensordaten

> Technisches Research-Dokument · Stand Juni 2026
> Scope: Dimensionierung und Betrieb der TimescaleDB-Hypertable `readings` in FOREMAN für hohe Insert-Last bei vielen Datenpunkten über viele Maschinen.
> Zielschema (real, aus GROUND_TRUTH §5):
>
> ```
> readings(
>   time          timestamptz NOT NULL,
>   data_point_id bigint       NOT NULL REFERENCES data_points(id),
>   value         double precision,
>   quality       smallint                       -- nullable
> )
> PRIMARY KEY (data_point_id, time)              -- Hypertable partitioniert auf time
> ```
>
> Es geht ausschließlich um FOREMANs eigene Datenbankschicht. Der externe Gedächtnis-Dienst wird hier nicht behandelt.
> Versionsbezug: TimescaleDB 2.18+ (Hersteller seit 2025 „Tiger Data", Produktname TimescaleDB). Die neue Hypercore-/Columnstore-API ist Primärpfad; die ältere Compression-API wird als Kompatibilitätshinweis genannt.

---

## 1. Fragestellung

FOREMAN nimmt analoge Messwerte und digitale I/O sehr vieler `data_points` als Zeitreihe auf. Die Schreiblast ist der dominierende Pfad: viele Datenpunkte × hohe Frequenz × viele Maschinen. Gleichzeitig lesen Dashboard und Drift-Reasoner aggregierte Verläufe, und die Plattform verspricht ein „Langzeitgedächtnis über Jahre". Diese drei Anforderungen — schnelles Schreiben, schnelles aggregiertes Lesen, günstige Langzeithaltung — ziehen in verschiedene Richtungen und müssen über die TimescaleDB-Tuning-Hebel ausbalanciert werden.

Beantwortet werden: Chunk-Intervall-Dimensionierung (2), Kompression/Columnstore (3.2), Continuous Aggregates (3.3), Insert-Pfad-Optimierung (3.4), Retention (3.5) und Single-Node-Betrieb in Docker Compose (5). Der Abschluss (4 und 6) benennt eine konkrete, baubare Konfiguration; Tradeoffs stehen im Vergleichsteil (3.6) davor.

---

## 2. Konzept-Grundlagen

**Hypertable & Chunks.** Eine Hypertable ist logisch eine Tabelle, physisch eine automatisch verwaltete Sammlung von **Chunks** — Partitionen entlang der Zeitachse. Jeder Chunk ist eine eigene PostgreSQL-Tabelle mit eigenen Indizes. Inserts landen fast immer im jüngsten Chunk; alte Chunks werden nur noch gelesen, komprimiert oder gelöscht. Das ist der Hebel hinter fast allem: Solange der **Index des aktiven Chunks in den RAM passt**, ist Insert billig; sobald er auf Platte ausgelagert werden muss, bricht die Insert-Rate ein, weil bei jedem Insert Indexseiten von Platte gelesen und zurückgeschrieben werden.

**Constraint zum Schema.** TimescaleDB verlangt, dass die Partitionsspalte (`time`) Teil jedes UNIQUE-Index ist. Der FOREMAN-PK `(data_point_id, time)` erfüllt das und ist zugleich die ideale Reihenfolge für „alle Werte eines Datenpunkts über die Zeit". Das passt zur Hauptabfrage und muss nicht geändert werden.

**Hypercore (Row + Columnstore).** Aktuelle TimescaleDB-Versionen führen Hypercore: junge Chunks liegen zeilenorientiert (schnelle Inserts/Punkt-Updates), ältere werden in einen **Columnstore** überführt (starke Kompression, schnelle analytische Scans). Der Übergang wird per Policy automatisiert.

**Continuous Aggregates (CAGGs).** Materialisierte, automatisch fortgeschriebene Roll-ups (z. B. Minuten-/Stunden-/Tagesmittel). Sie verlagern die Aggregationsarbeit vom Query-Zeitpunkt auf einen Hintergrundjob und sind die Grundlage schneller Dashboards und der ressourcenschonenden Langzeithaltung.

---

## 3. Tuning-Hebel einzeln

### 3.1 Chunk-Intervall (`chunk_time_interval`)

Der Default ist **7 Tage**. Die maßgebliche Faustregel (Tiger-Data-Doku): Das Intervall so wählen, dass **die Indizes aller gleichzeitig beschriebenen Chunks zusammen in höchstens ~25 % des Hauptspeichers** passen — über *alle* aktiven Hypertables, nicht pro Tabelle. Begründung siehe oben: Der aktive Index muss resident bleiben.

Für insert-heavy Daten mit vielen `data_points` heißt das in der Regel: **kürzere Chunks als der 7-Tage-Default.** Bei hoher Tagesvolumen-Last wächst der `(data_point_id, time)`-Index schnell; ein 7-Tage-Chunk hielte zu viel Index gleichzeitig „heiß". Ein **1-Tages-Intervall** ist der pragmatische Startwert: Er hält den aktiven Index klein, deckt sich mit täglichen Dashboard-/Schicht-Abfragemustern und lässt Kompression und Retention sauber tageweise greifen. Bei extrem hoher Last (aktiver Tages-Index > 25 % RAM) auf **6–12 h** verkürzen; bei geringer Last und überwiegend langen Zeitraum-Queries kann man Richtung mehrere Tage gehen. Zu *viele* winzige Chunks erzeugen Planungs-Overhead — die Balance ist „so groß wie möglich, solange der Hot-Index resident bleibt".

```sql
-- Hypertable anlegen (Migration/Alembic), 1-Tages-Chunks
SELECT create_hypertable(
  'readings', by_range('time', INTERVAL '1 day'),
  if_not_exists => TRUE
);
-- Nachträglich anpassen (gilt nur für NEUE Chunks):
SELECT set_chunk_time_interval('readings', INTERVAL '1 day');
```

### 3.2 Kompression / Columnstore (Hypercore)

Für das `readings`-Schema ist die Wahl klar:

- **`segmentby = data_point_id`** — niedrige bis mittlere Kardinalität, und genau die Spalte, nach der gefiltert wird. Innerhalb eines Chunks werden alle Werte eines Datenpunkts zusammen komprimiert; eine Query nach einem `data_point_id` liest nur dessen Segmente. Wichtig: pro Segment sollten **≥ ~100 Zeilen pro Chunk** anfallen, sonst leidet die Kompressionsrate. Bei 1-Tages-Chunks und nennenswerter Frequenz ist das pro Datenpunkt mühelos erfüllt.
- **`orderby = time DESC`** — Default und hier korrekt; sortiert die komprimierten Arrays zeitlich und beschleunigt „neueste zuerst"-Scans.

Erwartbare Kompression für numerische Sensorzeitreihen mit dieser Segmentierung: typischerweise **90–98 % Platzersparnis** (Delta-/Run-Length-Kodierung greift bei langsam veränderlichen Sensorwerten und bei digitalen 0/1-Strömen besonders gut).

Auswirkung: Analytische Scans auf komprimierten Chunks werden **schneller** (weniger I/O, spaltenweise). Punkt-`UPDATE`/`DELETE` und ungeordnete Backfills in komprimierte Chunks sind **teurer** als im Rowstore. FOREMANs Last ist append-only auf den jüngsten (unkomprimierten) Chunk — der teure Fall tritt also im Normalbetrieb nicht auf. Erst Chunks komprimieren, die **älter als der aktive Schreibhorizont** sind.

```sql
-- Neue Hypercore-API (TimescaleDB 2.18+)
ALTER TABLE readings SET (
  timescaledb.enable_columnstore = true,
  timescaledb.segmentby = 'data_point_id',
  timescaledb.orderby   = 'time DESC'
);
-- Chunks älter als 7 Tage automatisch in den Columnstore überführen
CALL add_columnstore_policy('readings', after => INTERVAL '7 days');

-- (Kompatibilität, ältere Versionen — gleicher Effekt:)
-- ALTER TABLE readings SET (timescaledb.compress,
--   timescaledb.compress_segmentby='data_point_id',
--   timescaledb.compress_orderby='time DESC');
-- SELECT add_compression_policy('readings', INTERVAL '7 days');
```

Der 7-Tage-Horizont hält rund eine Woche Rohdaten zeilenorientiert — genug für Live-Schreiben, Dashboard-Detailansicht und den anfänglichen Drift-Reasoner-Bedarf — und komprimiert alles Ältere.

### 3.3 Continuous Aggregates

Für FOREMAN lohnen sie sich klar, weil beide Hauptleser **aggregiert** lesen: das Dashboard zeigt Verläufe (nicht jeden Rohwert), und der Drift-Reasoner arbeitet ohnehin auf **1-Minuten-Aggregaten** (siehe Drift-Dokument: Downsampling auf 1 Sample/min als Median). Ein 1-Minuten-CAGG bedient beide und entlastet die Rohtabelle massiv.

Empfohlenes **hierarchisches** Muster (jede Ebene baut auf der darunter, nicht auf den Rohdaten — drastisch weniger Rechenlast):

```sql
-- Ebene 1: 1-Minuten-Aggregat direkt auf readings
CREATE MATERIALIZED VIEW readings_1m
WITH (timescaledb.continuous) AS
SELECT
  time_bucket(INTERVAL '1 minute', time) AS bucket,
  data_point_id,
  avg(value)    AS avg_value,
  min(value)    AS min_value,
  max(value)    AS max_value,
  count(*)      AS n,
  last(value, time) AS last_value
FROM readings
GROUP BY bucket, data_point_id
WITH NO DATA;

-- Ebene 2: 1-Stunde, hierarchisch auf readings_1m
CREATE MATERIALIZED VIEW readings_1h
WITH (timescaledb.continuous) AS
SELECT
  time_bucket(INTERVAL '1 hour', bucket) AS bucket,
  data_point_id,
  avg(avg_value) AS avg_value,
  min(min_value) AS min_value,
  max(max_value) AS max_value,
  sum(n)         AS n
FROM readings_1m
GROUP BY 1, 2
WITH NO DATA;

-- Ebene 3: 1-Tag, hierarchisch auf readings_1h (Langzeit-Gedächtnis)
CREATE MATERIALIZED VIEW readings_1d
WITH (timescaledb.continuous) AS
SELECT
  time_bucket(INTERVAL '1 day', bucket) AS bucket,
  data_point_id,
  avg(avg_value) AS avg_value,
  min(min_value) AS min_value,
  max(max_value) AS max_value,
  sum(n)         AS n
FROM readings_1h
GROUP BY 1, 2
WITH NO DATA;
```

**Real-time vs. materialisiert.** Seit v2.13 ist Real-time-Aggregation per Default **aus** (`materialized_only = true`): Queries sehen nur das bereits Materialisierte. Für das **1-Minuten-CAGG** empfiehlt sich Real-time **an**, damit Dashboard und Drift-Reasoner auch die jüngste, noch nicht materialisierte Minute sehen; die oberen Ebenen bleiben materialized-only (Stabilität, keine teuren Roh-Scans).

**Refresh-Policies.** `end_offset` muss größer sein als das Zeitfenster, in dem noch Daten eintreffen — sonst werden unfertige Buckets materialisiert und beim nächsten Lauf überschrieben.

```sql
ALTER MATERIALIZED VIEW readings_1m SET (timescaledb.materialized_only = false);

SELECT add_continuous_aggregate_policy('readings_1m',
  start_offset => INTERVAL '2 hours',
  end_offset   => INTERVAL '2 minutes',
  schedule_interval => INTERVAL '1 minute');

SELECT add_continuous_aggregate_policy('readings_1h',
  start_offset => INTERVAL '2 days',
  end_offset   => INTERVAL '1 hour',
  schedule_interval => INTERVAL '10 minutes');

SELECT add_continuous_aggregate_policy('readings_1d',
  start_offset => INTERVAL '15 days',
  end_offset   => INTERVAL '1 day',
  schedule_interval => INTERVAL '1 hour');
```

### 3.4 Insert-Pfad-Optimierung

Reihenfolge der Wirkung (stark → schwächer):

1. **Batch statt Einzeln.** Niemals Reading-für-Reading committen. Der F3-Adapter sammelt pro Tick alle Datenpunkte und schreibt sie gebündelt. Ein Batch von einigen Tausend Zeilen pro Roundtrip ist um Größenordnungen schneller als Einzel-Inserts.
2. **`COPY` statt `INSERT`** für große Batches. `COPY` (bzw. `asyncpg.copy_records_to_table`) ist der schnellste Massen-Schreibpfad in PostgreSQL und damit auch in TimescaleDB. Für moderate Batches sind mehrzeilige `INSERT … VALUES (…), (…), …` ausreichend; ab vielen Tausend Zeilen lohnt `COPY`.
3. **Wenige Indizes.** Jeder zusätzliche Index kostet bei jedem Insert. `readings` braucht nur den PK `(data_point_id, time)`. **Keine** weiteren Indizes auf der Rohtabelle anlegen — aggregierte Lesezugriffe laufen über die CAGGs, nicht über zusätzliche Roh-Indizes.
4. **Connection-Pooling.** Mit async SQLAlchemy 2.0 / `asyncpg` einen Pool nutzen (z. B. `pool_size` moderat, `max_overflow` begrenzt), damit Verbindungsaufbau nicht pro Batch anfällt. Bei sehr vielen kurzlebigen Verbindungen zusätzlich PgBouncer (Transaction-Pooling) erwägen — für die Single-Node-Workstation meist noch nicht nötig.
5. **In den jüngsten Chunk schreiben.** Append-only auf „jetzt" hält den Schreibpfad im unkomprimierten Hot-Chunk. Spätes Backfill in komprimierte/alte Chunks vermeiden bzw. bewusst als Sonderlauf behandeln.

```python
# foreman/adapters/ingest.py — Massen-Insert über asyncpg COPY
async def copy_readings(conn, rows: list[tuple]) -> None:
    # rows: (time, data_point_id, value, quality)
    await conn.copy_records_to_table(
        "readings",
        records=rows,
        columns=["time", "data_point_id", "value", "quality"],
    )
```

### 3.5 Retention

Hier wird der Konflikt „Insert-Last & Plattenplatz vs. Langzeitgedächtnis" sauber aufgelöst: **Rohdaten kurz halten, Aggregate lang.** Das Langzeitgedächtnis lebt in den CAGGs, nicht in der Rohtabelle — für Dashboard-Trends und Drift-Historie über Jahre genügen Minuten-/Stunden-/Tageswerte; Rohwerte im Sekundentakt braucht niemand nach Monaten.

```sql
-- Rohdaten: 90 Tage (deckt Detailanalyse + Drift-Warm-up reichlich)
SELECT add_retention_policy('readings', drop_after => INTERVAL '90 days');

-- Aggregate gestaffelt aufbewahren:
SELECT add_retention_policy('readings_1m', drop_after => INTERVAL '1 year');
SELECT add_retention_policy('readings_1h', drop_after => INTERVAL '5 years');
-- readings_1d: KEINE Retention -> unbegrenztes Langzeitgedächtnis
```

Retention löscht ganze Chunks (billig, kein zeilenweises `DELETE`). Wichtig: Die Retention der Rohtabelle darf nicht kürzer sein als das `start_offset` der CAGG-Refresh-Policies, sonst fehlen Quelldaten beim Materialisieren — 90 Tage liegen weit darüber.

### 3.6 Vergleich der Tuning-Hebel

| Hebel | Wirkung | Aufwand | Risiko |
|---|---|---|---|
| `chunk_time_interval` = 1 Tag (statt 7) | hält Hot-Index resident → stabile Insert-Rate; saubere tageweise Kompression/Retention | gering (ein Parameter) | zu kurz → Chunk-Overhead; zu lang → Index fällt aus RAM, Insert bricht ein |
| Columnstore `segmentby=data_point_id`, `orderby=time DESC` | 90–98 % Platz, schnellere analytische Scans | gering (DDL + Policy) | teure Updates/Backfills in komprimierte Chunks (für append-only irrelevant) |
| Continuous Aggregates (1m→1h→1d, hierarchisch) | schnelle Dashboards, billige Langzeithaltung, entlastet Rohtabelle | mittel (Views + Policies + Refresh-Tuning) | falsches `end_offset` → unfertige Buckets; Real-time-Modus kostet etwas Query-Zeit |
| Batch + `COPY` Insert-Pfad | Insert-Durchsatz um Größenordnungen höher | gering-mittel (Adapter-Code) | größere Transaktionen, mehr RAM pro Batch |
| Wenige Indizes (nur PK) | jeder vermiedene Index spart Insert-Kosten | gering (Disziplin) | spätere Roh-Punkt-Queries langsamer (über CAGGs abfangen) |
| Connection-Pooling (asyncpg/SQLAlchemy) | kein Verbindungs-Overhead pro Batch | gering | Pool zu groß → zu viele Backends auf Single-Node |
| Retention (Roh 90 d, Aggregate gestaffelt) | begrenzt Plattenwachstum, erhält Langzeit-Aggregate | gering (Policies) | Roh-Retention < CAGG-start_offset → Materialisierungslücken |

---

## 4. Konkrete Empfehlung für FOREMAN

Die getroffene Konfiguration, direkt auf das `readings`-Schema:

- **Chunk-Intervall: 1 Tag.** Startwert; bei aktivem Tages-Index > 25 % RAM auf 12 h bzw. 6 h verkürzen.
- **Columnstore: `segmentby = data_point_id`, `orderby = time DESC`, Policy `after => 7 days`.** Rund eine Woche heiß/zeilenorientiert, alles Ältere komprimiert (erwartet 90–98 % Ersparnis).
- **Continuous Aggregates: hierarchisch 1 min → 1 h → 1 d.** 1-Minuten-CAGG mit Real-time an (Dashboard + Drift-Reasoner), obere Ebenen materialized-only.
- **Insert-Pfad: Batch + `COPY` via asyncpg, Connection-Pool, nur der PK als Index.**
- **Retention: Rohdaten 90 Tage; `readings_1m` 1 Jahr; `readings_1h` 5 Jahre; `readings_1d` unbegrenzt** (= Langzeitgedächtnis).

### 4.1 Kopierbares Gesamt-Setup (Migration)

```sql
-- 1) Hypertable mit 1-Tages-Chunks
SELECT create_hypertable('readings', by_range('time', INTERVAL '1 day'),
  if_not_exists => TRUE);

-- 2) Columnstore/Hypercore
ALTER TABLE readings SET (
  timescaledb.enable_columnstore = true,
  timescaledb.segmentby = 'data_point_id',
  timescaledb.orderby   = 'time DESC'
);
CALL add_columnstore_policy('readings', after => INTERVAL '7 days');

-- 3) Continuous Aggregates (Definitionen siehe 3.3) + Policies (siehe 3.3)
--    readings_1m (real-time), readings_1h, readings_1d

-- 4) Retention
SELECT add_retention_policy('readings',     drop_after => INTERVAL '90 days');
SELECT add_retention_policy('readings_1m',  drop_after => INTERVAL '1 year');
SELECT add_retention_policy('readings_1h',  drop_after => INTERVAL '5 years');
-- readings_1d: keine Retention
```

### 4.2 Begleitende PostgreSQL-Parameter (Workstation, z. B. 64 GB RAM)

```
shared_buffers              = 16GB     # ~25 % RAM
effective_cache_size        = 48GB     # ~75 % RAM
work_mem                    = 64MB     # pro Sort/Hash; bei vielen Workern vorsichtig
maintenance_work_mem        = 2GB      # Kompression/Index-Builds
max_worker_processes        = 16
timescaledb.max_background_workers = 8 # Policies/CAGG-Refreshes
wal_compression             = on
checkpoint_timeout          = 15min
max_wal_size                = 8GB      # weniger Checkpoints unter Insert-Last
synchronous_commit          = off      # nur falls minimaler Datenverlust bei Crash tolerierbar
```

`timescaledb-tune` kann diese Werte hardware-abhängig vorbelegen; `synchronous_commit = off` nur bewusst setzen (Durchsatz vs. potenzieller Verlust der letzten Transaktionen bei Crash).

---

## 5. Betriebsaspekte (Docker Compose, Single-Node)

**Image & Volume.** Das Standard-Postgres-Image hat **kein** TimescaleDB — `timescale/timescaledb-ha:pg16` (bzw. passende pg17-Variante) verwenden; es bringt TimescaleDB und die nötigen Extensions mit. PGDATA auf ein **benanntes Volume** legen, niemals in die Container-Schreibschicht.

```yaml
services:
  timescaledb:
    image: timescale/timescaledb-ha:pg16
    environment:
      POSTGRES_DB: foreman
      POSTGRES_PASSWORD_FILE: /run/secrets/pg_password   # Secret, nicht im Compose-Klartext
    volumes:
      - tsdb_data:/var/lib/postgresql/data
      - ./postgres.conf:/etc/postgresql/postgresql.conf:ro
    command: ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
    shm_size: "1g"                 # genügend Shared Memory für Parallel-Workers
    deploy:
      resources:
        limits:   { memory: 56g }   # RAM für DB reservieren, OS-Reserve lassen
volumes:
  tsdb_data:
```

**Backup.** Logische Dumps mit `pg_dump` funktionieren, brauchen bei Hypertables aber die TimescaleDB-Restore-Schritte (`SELECT timescaledb_pre_restore();` … Restore … `SELECT timescaledb_post_restore();`). Für ein wachsendes Produktivsystem ist **physisches Backup mit pgBackRest** (Basis-Backup + WAL-Archiv, Point-in-Time-Recovery) die robustere Wahl; ein periodischer Volume-Snapshot bei gestopptem/quiesziertem Dienst ist die einfachste Fallback-Variante. Backups regelmäßig **testweise zurückspielen** — ungetestete Backups sind keine.

**Realistische Grenzen einer Workstation-Instanz.** Eine 16-Kern/64-GB-Maschine mit NVMe trägt für ein MVP/Pilot eine sehr hohe Insert-Rate (Größenordnung Hunderttausende Zeilen/s bei `COPY` und gut dimensionierten Chunks). Die harten Grenzen sind in dieser Reihenfolge: **RAM** (Hot-Chunk-Index muss resident bleiben → über Chunk-Intervall steuern), **Disk-I/O/IOPS** (NVMe Pflicht; HDD scheidet aus), **Plattenkapazität** (über Kompression + Retention beherrscht). Single-Node hat keine Hochverfügbarkeit — Ausfallsicherheit kommt erst mit Replikation (späterer Skalierungspfad, nicht MVP-Scope).

---

## 6. Offene Punkte

- **Reale Insert-Rate messen, dann Chunk-Intervall final setzen.** 1 Tag ist begründeter Startwert; die 25-%-RAM-Regel lässt sich erst mit echten SPS-Datenraten (Zeilen/s, Index-Wachstum/Tag) scharf rechnen. Nach erstem Lastlauf verifizieren.
- **`quality`-Behandlung.** Ob NULL/Bad-Quality-Werte in `readings` landen oder vorgefiltert werden, beeinflusst Volumen und CAGG-Semantik (z. B. `avg(value) FILTER (WHERE quality = good)`). Mit dem Adapter-Design abstimmen.
- **Digitale I/O vs. analoge Werte.** Beide liegen in `readings`. Für 0/1-Ströme sind andere Aggregate sinnvoll (Zustandsdauer, Flankenzahl) als `avg/min/max`. Ggf. getrennte CAGGs oder ein Typ-Filter über `data_points.kind`.
- **Backfill-Strategie.** Wenn der digitale Zwilling historische Zeiträume nachlädt, fällt das in alte/komprimierte Chunks — als bewussten Sonderlauf planen (Dekompression/Recompression), nicht über den Live-Insert-Pfad.
- **`synchronous_commit`.** Für maximalen Insert-Durchsatz verlockend auszuschalten; die Entscheidung hängt davon ab, wie viel potenzieller Verlust der letzten Sekunden bei einem Crash akzeptabel ist. Pro Deployment festlegen.
- **Skalierung über eine Node hinaus.** Read-Replikate/HA und ggf. Mehr-Node sind außerhalb des MVP; bei Produktivkunden mit Halle erneut bewerten.

---

## Quellen

- Tiger Data / TimescaleDB-Dokumentation (Stand 2025/2026):
  - Hypertables & Query-Performance / Chunk-Sizing (25-%-RAM-Regel). https://www.tigerdata.com/docs/use-timescale/latest/hypertables/improve-query-performance
  - Hypercore / Columnstore, `add_columnstore_policy()`. https://docs.timescale.com/api/latest/hypercore/add_columnstore_policy/ · https://www.tigerdata.com/docs/build/columnar-storage/setup-hypercore
  - Continuous Aggregates (About / Refresh-Policies, Real-time vs. materialized). https://www.tigerdata.com/docs/use-timescale/latest/continuous-aggregates/about-continuous-aggregates · https://www.tigerdata.com/docs/use-timescale/latest/continuous-aggregates/refresh-policies
  - Data-Retention-Policies (`add_retention_policy`). https://github.com/timescale/docs/blob/latest/use-timescale/data-retention/create-a-retention-policy.md
- PostgreSQL-Dokumentation: `COPY`, WAL/Checkpoints, Speicherparameter. https://www.postgresql.org/docs/current/
- asyncpg — `copy_records_to_table`. https://magicstack.github.io/asyncpg/current/
- Praxis-Benchmarks/Erfahrungsberichte 2025/2026 (Kompressionsraten, Chunk-/CAGG-Tuning): TimescaleDB-Compression-Fallstudien (90 % Reduktion), Memory-Tuning-Artikel (shared_buffers/work_mem/Chunk-Sizing), Docker-Betriebsleitfäden. Quellen über die obige Suche (dev.to, oneuptime, mydba.dev) — vor Produktivsetzung gegen die offizielle Doku der eingesetzten Version prüfen.

> Hinweis: Konfigurationswerte sind begründete Startwerte für eine Single-Node-Workstation, keine universell optimalen Konstanten. Vor Produktivsetzung gegen reale Insert-Raten und die exakt eingesetzte TimescaleDB-Version verifizieren.
