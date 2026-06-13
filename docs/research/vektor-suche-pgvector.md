# Vektor-Suche in PostgreSQL (pgvector) für FOREMAN-Schichtberichte

> Technisches Research-Dokument · Stand Juni 2026
> Scope: semantische Suche über Werker-Notizen / Schichtberichte (`worker_notes.text`, deutscher Freitext) via Embeddings in **FOREMANs eigener PostgreSQL** mit der pgvector-Extension. Anwendungsfall: „hatten wir dieses Vibrationsmuster schon mal" — Ähnlichkeitssuche statt Stichwort-Gleichheit, im selben System wie die relationalen Daten.
> Schemabezug (GROUND_TRUTH §5): `worker_notes(id, machine_id, shift, text, classification, embedding vector(1024), author, created_at)`.
> Das externe Gedächtnis-Substrat ist **nicht** Gegenstand dieses Dokuments; es geht ausschließlich um FOREMANs eigene Embedding-/Index-Schicht.
> Versionsbezug: pgvector **0.8.2** (≥ 0.8.2 zwingend — 0.8.2 behebt CVE-2026-3172, Buffer-Overflow bei parallelen HNSW-Builds). PostgreSQL 16+.

---

## 1. Fragestellung

Schichtberichte sind kurzer, fachsprachlicher deutscher Freitext („Lager an Spindel 3 läuft heiß, Geräusch wie letzte Woche an der Schwestermaschine"). Eine Stichwortsuche findet das verwandte Ereignis nur, wenn exakt dieselben Wörter fielen. Semantische Suche über Embeddings findet es über die *Bedeutung* — genau der Kern von FOREMANs „hatten wir das schon mal". Da die Vektoren in derselben PostgreSQL liegen wie die relationalen Daten, lässt sich Ähnlichkeit mit harten Filtern (Maschine, Komponente, Zeitraum) in *einer* Query kombinieren.

Beantwortet werden: Indextypen HNSW vs. IVFFlat (2/3), Distanzmetrik (3.2), mehrsprachige Embedding-Modelle für deutschen Fachtext (4), hybride Suche Vektor + Volltext (5), Chunking/Vorverarbeitung (6), Betrieb (7). Abschnitt 8 benennt die getroffene Wahl mit kopierbarer SQL; Tradeoffs stehen in den Vergleichstabellen davor.

---

## 2. Index-Grundlagen

**Das Problem.** Exakte Nächste-Nachbar-Suche (Brute Force) vergleicht den Query-Vektor mit *jedem* gespeicherten Vektor — exakt, aber O(n) pro Query. Ab einigen zehntausend Zeilen wird das zu langsam. Daher **Approximate Nearest Neighbor (ANN)**: ein Index, der mit kontrollierbarem Recall-Verlust drastisch schneller die *wahrscheinlich* nächsten Nachbarn liefert. pgvector bietet zwei ANN-Indextypen — HNSW und IVFFlat — plus die Option, ganz ohne Index exakt zu suchen (sinnvoll bei kleinen Beständen).

**HNSW (Hierarchical Navigable Small World).** Ein mehrschichtiger Graph (Malkov & Yashunin, 2016/2018): obere Schichten dünn für weite Sprünge, untere dicht für lokale Feinsuche. Eine Query „navigiert" greedy von oben nach unten zum nächsten Nachbarn. Logarithmische Suchzeit, sehr gutes Recall/Latenz-Verhältnis, **inkrementell aufbaubar** (Vektoren können einzeln eingefügt werden, kein Trainingsschritt). Preis: höherer Speicherbedarf und langsamerer Build.

- Parameter (Build): `m` (Kanten pro Knoten, Default 16; höher = besseres Recall + mehr Speicher), `ef_construction` (Kandidatenliste beim Bau, Default 64; höher = besseres Recall + langsamerer Build).
- Parameter (Query): `hnsw.ef_search` (Default 40; höher = besseres Recall bei *sublinearem* Latenzanstieg) — zur Laufzeit pro Session einstellbar.

**IVFFlat (Inverted File with Flat compression).** Clustert die Vektoren bei Build-Zeit in `lists` Zellen (k-Means); eine Query durchsucht nur die `probes` nächsten Zellen. Geringerer Speicher, schnellerer Build — aber: braucht **repräsentative Daten zum Build-Zeitpunkt** (Training), reagiert schlechter auf stark wachsende/driftende Bestände (Cluster veralten → Rebuild nötig), und die Suchzeit wächst **linear** mit `probes`.

- Parameter (Build): `lists` (Zahl der Cluster; Faustregel `rows/1000` bis 1 Mio., darüber `sqrt(rows)`).
- Parameter (Query): `ivfflat.probes` (Default 1; sinnvoll ~`sqrt(lists)` bzw. 10–50; höher = besseres Recall + linear langsamer).

---

## 3. Indexvergleich

| Indextyp | Recall (tunebar) | Latenz | Speicher | Build-Zeit | Update-/Insert-Verhalten |
|---|---|---|---|---|---|
| **HNSW** | hoch, fein steuerbar (`ef_search`) | **niedrig**, log. Skalierung | hoch | langsam | **inkrementell**, Einzel-Inserts gut; kein Rebuild bei Wachstum |
| **IVFFlat** | mittel–hoch (`probes`), linear erkauft | mittel, linear mit `probes` | niedrig | schnell | braucht Trainingsdaten; Cluster veralten → periodischer Rebuild |
| **Kein Index (exakt)** | 100 % | hoch ab ~10⁴ Zeilen | minimal | — | trivial (nichts zu pflegen) |

**Lesart für FOREMAN.** Werker-Notizen wachsen **kontinuierlich** (laufende Inserts), und der Bestand ist für das MVP moderat (Tausende bis niedrige Zehntausende Notizen, nicht Millionen). Beides spricht für **HNSW**: es nimmt neue Vektoren ohne Rebuild auf und liefert das beste Recall/Latenz-Verhältnis; der höhere Speicher ist bei dieser Größenordnung irrelevant (einige zehntausend 1024-dim-Vektoren sind wenige hundert MB). IVFFlat lohnt erst bei sehr großen, eher statischen Beständen mit Speicherdruck — nicht FOREMANs Profil. Bei sehr kleinem Anfangsbestand (wenige tausend Notizen) ist sogar **gar kein Index** (exakte Suche) vertretbar, bis das Volumen den HNSW-Build rechtfertigt.

### 3.2 Distanzmetrik

pgvector bietet drei Operatorklassen: `vector_cosine_ops` (`<=>`, Kosinus-Distanz), `vector_l2_ops` (`<->`, euklidisch) und `vector_ip_ops` (`<#>`, negatives inneres Produkt). Die Wahl folgt dem **Embedding-Modell**, nicht der Vorliebe:

- Moderne Satz-Embeddings (BGE-M3, multilingual-e5, Qwen3-Embedding) werden auf **Kosinus-Ähnlichkeit** trainiert und liefern Vektoren, bei denen die Richtung die Semantik trägt, nicht die Länge. → **Cosine** (`vector_cosine_ops`).
- Bei **L2-normierten** Vektoren sind Cosine, Inner Product und (monoton) L2 rangäquivalent; Inner Product ist dann minimal billiger, aber Cosine ist die robuste, intentionsklare Default-Wahl.
- Reines L2 ist nur sinnvoll, wenn das Modell explizit auf euklidische Distanz trainiert wurde — bei den hier relevanten Modellen nicht der Fall.

**Festlegung: Cosine.** Für FOREMAN: Embeddings beim Schreiben L2-normieren und `vector_cosine_ops` verwenden — damit ist die Metrik-Frage robust und modellkonform erledigt.

---

## 4. Embedding-Modell-Vergleich (deutscher Industrie-Freitext)

Anforderungen: gute Qualität auf **deutschem Fachtext**, **lokal lauffähig** (Air-Gap-Ziel, RTX-4090-Workstation), **permissive Lizenz** (kommerzieller/Freelance-Pfad), Dimension passend zum Schema (`vector(1024)`).

| Modell | Sprache / Deutsch | Dimension | Lizenz | Lokale Eignung / Kosten |
|---|---|---|---|---|
| **BGE-M3** (BAAI) | 100+ Sprachen, stark auf DE | **1024** (dense) | **MIT** (permissiv) | sehr gut: ~560 M Param, läuft lokal (GPU/CPU); dense **+ sparse + multi-vector** in einem Modell (hybrid-nativ) |
| **multilingual-e5-large** (intfloat) | 100 Sprachen, DE solide (MTEB de ≈ 71) | 1024 | **MIT** | gut; benötigt `query:`/`passage:`-Präfixe; 24-Layer, lokal lauffähig |
| **Qwen3-Embedding-0.6B** (Alibaba) | 100+ Sprachen, Top-MMTEB (8B = #1, 70.6) | bis 1024 (MRL) | **Apache 2.0** | 0.6B lokal gut; 4B/8B stärker, aber teurer; 32k-Kontext |
| **jina-embeddings-v3** (Jina) | mehrsprachig, lange Kontexte (8192) | bis 1024 (MRL) | **CC-BY-NC-4.0 (nicht-kommerziell)** | technisch stark, aber **Lizenz blockiert** kommerziellen Einsatz → für FOREMAN ausgeschlossen |

**Lesart.** `jina-v3` fällt an der nicht-kommerziellen Lizenz aus (gleiches Muster wie alibi-detect im Drift-Kontext: technisch gut, lizenzrechtlich für den Freelance-/Produktpfad unbrauchbar). Verbleiben drei MIT/Apache-Modelle. **BGE-M3** ist für FOREMAN die naheliegende Wahl: 1024-dim (passt 1:1 zum `vector(1024)`-Schema), MIT, starke Deutsch-Performance, lokal lauffähig — und es liefert in *einem* Modell dense-, sparse- und multi-vector-Embeddings, was die hybride Suche (Abschnitt 5) ohne zweites Modell ermöglicht. `multilingual-e5-large` ist die gleichwertige Ausweichoption (1024, MIT), kostet aber die Präfix-Disziplin. `Qwen3-Embedding-0.6B` (Apache 2.0) ist attraktiv, wenn man ohnehin im Qwen-Ökosystem ist (FOREMAN nutzt Qwen3 als LLM) und MRL-Flexibilität will. MTEB-/MMTEB-Ranglisten bewegen sich schnell — vor Produktivsetzung den aktuellen deutschen Benchmark-Stand prüfen.

---

## 5. Hybride Suche: Vektor + Volltext

**Warum hybrid.** Dense-Embeddings sind stark bei *Bedeutung* (Paraphrase, Synonyme: „läuft heiß" ≈ „Übertemperatur"), aber schwach bei *exakten Tokens* — Fehlercodes (`F-1042`), Bauteilnummern, Abkürzungen, Eigennamen. Genau die sind im Industrie-Freitext häufig und identifizierend. PostgreSQL-Volltext (BM25-artiges Ranking über `tsvector`/`ts_rank`) trifft diese exakt. Die Kombination beider deckt beide Fehlerarten ab und ist für FOREMANs Fachsprache **klar sinnvoll**.

**Gewichtung via Reciprocal Rank Fusion (RRF).** Statt heterogene Scores (Kosinus-Distanz vs. `ts_rank`) zu normalisieren und zu mischen, fusioniert RRF die **Ränge** beider Trefferlisten: `score(d) = Σ 1/(k + rank_i(d))`, typisch `k = 60` (Cormack et al., 2009). Das ist robust, parameterarm und der De-facto-Standard für Hybrid-Retrieval — kein fragiles Score-Tuning nötig.

Deutsche Volltextkonfiguration: `to_tsvector('german', text)` (Stemming, Stoppwörter) + GIN-Index; Query über `websearch_to_tsquery('german', :q)`.

```sql
-- Volltext-Spalte + GIN-Index (zusätzlich zur Vektor-Spalte)
ALTER TABLE worker_notes
  ADD COLUMN text_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('german', coalesce(text, ''))) STORED;
CREATE INDEX ON worker_notes USING gin (text_tsv);

-- Hybride Suche mit Reciprocal Rank Fusion (k = 60)
WITH vector_hits AS (
  SELECT id, row_number() OVER (ORDER BY embedding <=> :q_vec) AS rnk
  FROM worker_notes
  WHERE machine_id = :machine_id           -- harter Filter, im selben System
  ORDER BY embedding <=> :q_vec
  LIMIT 50
),
fulltext_hits AS (
  SELECT id, row_number() OVER (
           ORDER BY ts_rank(text_tsv, websearch_to_tsquery('german', :q_text)) DESC
         ) AS rnk
  FROM worker_notes
  WHERE machine_id = :machine_id
    AND text_tsv @@ websearch_to_tsquery('german', :q_text)
  LIMIT 50
)
SELECT id,
       coalesce(1.0/(60 + v.rnk), 0) + coalesce(1.0/(60 + f.rnk), 0) AS rrf_score
FROM vector_hits v
FULL OUTER JOIN fulltext_hits f USING (id)
ORDER BY rrf_score DESC
LIMIT 10;
```

---

## 6. Chunking & Vorverarbeitung

**Kein Chunking.** Schichtberichte sind kurz (Sätze bis wenige Absätze) und liegen weit unter dem Kontextfenster der Modelle (BGE-M3/e5: ausreichend; jina/Qwen3: 8k–32k Token). Daher **Whole-Document-Embedding pro Notiz** — eine Notiz, ein Vektor. Chunking würde hier nur die Granularität verschlechtern (Sub-Treffer ohne Mehrwert) und Komplexität erzeugen. Erst falls künftig lange, mehrthemige Berichte auftreten, lohnt satz-/absatzweises Chunking.

**Fachjargon & Abkürzungen.** Zwei Hebel: (1) Die **hybride Suche** fängt exakte Abkürzungen/Codes über den Volltext-Pfad ab, wo das Embedding paraphrasiert. (2) Optional eine **Normalisierungs-/Synonymschicht** vor der Indexierung (Abkürzungs-Wörterbuch „Sp." → „Spindel", domänenspezifische Synonyme als PostgreSQL-`thesaurus`-Dictionary in der FTS-Konfiguration). Für das MVP genügt Hybrid + ggf. ein kleines Synonym-Mapping; ein gepflegtes Fach-Thesaurus ist ein späterer Ausbau.

---

## 7. Betriebsaspekte

- **Index-Wartung bei laufenden Inserts.** HNSW nimmt neue Zeilen inkrementell auf — kein Rebuild nötig. Den Index nach dem initialen Bulk-Load anlegen (schneller als Zeile-für-Zeile-Aufbau); im laufenden Betrieb `CREATE INDEX CONCURRENTLY` nutzen, um Schreibsperren zu vermeiden. Wegen CVE-2026-3172 **pgvector ≥ 0.8.2** verwenden (Fix für parallele HNSW-Builds).
- **Embedding-Spalte & Versionierung.** Das verwendete Modell **mitschreiben** (`embedding_model text`, z. B. `bge-m3@v1`), damit bei Modellwechsel klar ist, welche Vektoren in welchem Raum liegen — Vektoren verschiedener Modelle sind **nicht** vergleichbar.
- **Re-Embedding bei Modellwechsel.** Modellwechsel = neuer Vektorraum. Vorgehen: neue Spalte/Tabelle (`embedding_v2 vector(d2)`), gesamten Bestand neu einbetten (Batch-Job), Index auf der neuen Spalte bauen, Query-Pfad umschalten, alte Spalte nach Validierung droppen. Kein „In-Place"-Mischen.
- **Dimensions-Migration.** `vector(1024)` ist fix typisiert; eine andere Dimension braucht eine neue Spalte (s. o.). Bei BGE-M3 bleibt es bei 1024 → keine Migration nötig, solange das Modell gehalten wird. MRL-Modelle (Qwen3/jina) erlaubten kleinere Dimensionen, aber das ist eine bewusste Schema-Entscheidung, kein Live-Switch.
- **Speicher/Performance.** HNSW-Graph im RAM beschleunigt Queries; `maintenance_work_mem` für den Build hochsetzen. `halfvec` (16-bit) halbiert den Vektor-Speicher bei meist vernachlässigbarem Recall-Verlust — Option, falls der Bestand groß wird.

---

## 8. Empfehlung für FOREMAN

- **Index: HNSW**, Operatorklasse **`vector_cosine_ops`**. Parameter `m = 16`, `ef_construction = 200` (Build), `hnsw.ef_search = 40` als Query-Start (bei zu niedrigem Recall hochsetzen). Begründung: kontinuierliche Inserts ohne Rebuild, bestes Recall/Latenz-Verhältnis, moderater Bestand macht den Speicher irrelevant. (Bei sehr kleinem Anfangsbestand zunächst ohne Index/exakt, HNSW ab ~10⁴ Notizen.)
- **Distanz: Cosine**; Embeddings beim Schreiben L2-normieren.
- **Embedding-Modell: BGE-M3** (1024-dim, **MIT**, lokal, stark auf Deutsch, hybrid-nativ). Passt 1:1 zum `vector(1024)`-Schema und zum Air-Gap-/Freelance-Pfad. Ausweich: `multilingual-e5-large` (MIT) oder `Qwen3-Embedding-0.6B` (Apache 2.0). **Kein jina-v3** (CC-BY-NC).
- **Suche: hybrid**, Vektor (`<=>`) + deutscher Volltext (`to_tsvector('german', …)`), fusioniert per **RRF (k = 60)**. Harte Filter (`machine_id`, Zeitraum) in derselben Query.
- **Chunking: keines** — eine Notiz, ein Vektor. Fachjargon/Codes über den Volltext-Pfad + optionales Synonym-Mapping.
- **Betrieb:** pgvector **≥ 0.8.2**; `embedding_model` mitschreiben; Re-Embedding bei Modellwechsel über neue Spalte; Index via `CREATE INDEX CONCURRENTLY`.

### 8.1 Kopierbares Setup (Migration)

```sql
-- Extension (einmalig)
CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector >= 0.8.2

-- worker_notes.embedding existiert bereits als vector(1024) (GROUND_TRUTH §5).
-- Modellversion mitschreiben (Vektoren verschiedener Modelle sind unvergleichbar):
ALTER TABLE worker_notes ADD COLUMN IF NOT EXISTS embedding_model text;

-- HNSW-Index, Cosine. CONCURRENTLY im laufenden Betrieb.
CREATE INDEX CONCURRENTLY IF NOT EXISTS worker_notes_embedding_hnsw
  ON worker_notes USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 200);

-- Deutscher Volltext für den Hybrid-Pfad:
ALTER TABLE worker_notes
  ADD COLUMN IF NOT EXISTS text_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('german', coalesce(text, ''))) STORED;
CREATE INDEX CONCURRENTLY IF NOT EXISTS worker_notes_tsv_gin
  ON worker_notes USING gin (text_tsv);

-- Query-Laufzeit (pro Session/Connection):
SET hnsw.ef_search = 40;
```

Der Embedding-Service (lokal, BGE-M3) bettet `text` beim Insert ein, normiert L2 und schreibt `embedding` + `embedding_model`. Die hybride RRF-Query aus Abschnitt 5 liefert die Treffer für „hatten wir das schon mal".

---

## 9. Offene Punkte

- **Modell final benchmarken.** BGE-M3 vs. multilingual-e5 vs. Qwen3-0.6B auf **echten Schichtberichten** (deutscher Werkstatt-Jargon) messen — die MTEB-Allgemeinscores sagen wenig über genau diese Domäne. Kleiner gelabelter Retrieval-Testsatz aus realen Notizen.
- **HNSW-Parameter an Realdaten.** `m`/`ef_construction`/`ef_search` gegen gemessenen Recall justieren, sobald Notiz-Volumen und Query-Muster real sind.
- **Reranker?** Ob ein nachgelagerter Cross-Encoder-Reranker (z. B. BGE-Reranker, Qwen3-Reranker) den Mehraufwand lohnt, an der Trefferqualität entscheiden — erst nach Hybrid-Baseline.
- **Synonym-/Abkürzungs-Thesaurus.** Umfang eines gepflegten Fach-Wörterbuchs (Werkstatt-Abkürzungen) gegen den Pflegeaufwand abwägen; ggf. aus realen Notizen halbautomatisch ableiten.
- **Kopplung an semantische Events.** Ob auch `maintenance_events`/`alarms`-Beschreibungen mit-eingebettet werden (gemeinsamer Suchraum „hatten wir das"), ist eine Produktentscheidung — technisch dieselbe Pipeline.
- **Personenbezug im Freitext.** Die Embeddings entstehen aus `worker_notes.text` **nach** der NER-Maskierung (siehe `anonymisierung-werkerdaten.md`); sicherstellen, dass eingebettet wird, was maskiert wurde, nicht der Rohtext.

---

## Quellen

- pgvector (BSD-ähnliche Lizenz), Doku & CHANGELOG; Release 0.8.0 / 0.8.2 (CVE-2026-3172). https://github.com/pgvector/pgvector · https://www.postgresql.org/about/news/pgvector-082-released-3245/
- Y. Malkov, D. Yashunin, *Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs*, IEEE TPAMI (2018; arXiv:1603.09320). HNSW.
- pgvector Index-Tuning (HNSW `m`/`ef_construction`/`ef_search`, IVFFlat `lists`/`probes`), Praxis-Benchmarks 2025: dbi-services, Instaclustr, dev.to (HNSW vs. IVFFlat). Vor Produktivsetzung gegen die offizielle pgvector-Doku der eingesetzten Version prüfen.
- G. Cormack, C. Clarke, S. Büttcher, *Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods*, SIGIR 2009 (RRF, k≈60).
- Embedding-Modelle: BGE-M3 (BAAI, MIT, 1024-dim dense + sparse + multi-vector) https://huggingface.co/BAAI/bge-m3 · multilingual-e5-large (intfloat, MIT, 1024) https://huggingface.co/intfloat/multilingual-e5-large · Qwen3-Embedding (Alibaba, Apache 2.0, MRL, 0.6B/4B/8B) https://qwenlm.github.io/blog/qwen3-embedding/ · jina-embeddings-v3 (CC-BY-NC-4.0, nicht-kommerziell) https://huggingface.co/jinaai/jina-embeddings-v3
- MTEB / MMTEB (Massive [Multilingual] Text Embedding Benchmark), Leaderboard & *Maintaining MTEB* (2025). https://huggingface.co/spaces/mteb/leaderboard · arXiv:2506.21182 · deutsche Benchmarks: mteb-de / tecb-de.
- PostgreSQL-Volltextsuche (`tsvector`, `to_tsvector('german', …)`, `ts_rank`, `websearch_to_tsquery`). https://www.postgresql.org/docs/current/textsearch.html

> Hinweis: Index- und Modell-Empfehlung nach dokumentiertem Stand 2025/2026. Embedding-Ranglisten und Library-Versionen bewegen sich schnell — vor dem Bau gegen den aktuellen MTEB-Stand und die eingesetzte pgvector-Version prüfen.
