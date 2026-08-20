# ============================================================
#  FOREMAN — substrate/backfill.py
#  Zweck: Additiver, idempotenter Backfill bereits gespiegelter
#         `semantic_events`, deren Substrat-Dual-Write fehlte (substrate_ref
#         IS NULL) — typisch die Park-Seed-Ereignisse, die bei leerem Substrat
#         (SUBSTRATE_BASE_URL="") nur in der DB landeten. Schreibt sie über
#         SubstrateClient.remember(namespace=foreman) nachträglich ins
#         Gedächtnis-Substrat und persistiert die gewonnene Referenz.
#  Architektur-Einordnung: Ingestion/Substrat-Brücke (Schicht 2). Gegenstück zu
#         ingestion/semantic.py: dort entsteht die Spiegel-Zeile, hier wird der
#         best-effort gescheiterte Dual-Write nachgeholt.
#  Invarianten (Leitplanken des Auftrags):
#    - ADDITIV: einzige DB-Schreibung ist `semantic_events.substrate_ref`; keine
#      Readings/Events/Topologie werden angefasst, keine Zeilen neu angelegt.
#    - IDEMPOTENT: es werden ausschließlich Zeilen mit substrate_ref IS NULL
#      bearbeitet; nach erfolgreichem remember wird die Referenz gesetzt und SOFORT
#      committet (pro Zeile, nicht je Batch), ein Re-Run findet die Zeile dann nicht
#      mehr. Das Duplikat-Fenster (remember ok, dann Absturz vor Commit) bleibt so
#      auf höchstens EINE Erinnerung beschränkt.
#    - ISOLIERT: der remember läuft über den foreman-Namespace des Clients
#      (source=substrate:foreman in der Fassade).
#    - COLD-START-FEST: der erste Substrat-Call ist kalt (>10s); Batch + Retry
#      brechen nicht beim ersten Timeout ab.
#  Content-Treue: Der ans Substrat gesendete Text wird NICHT neu erfunden,
#         sondern deterministisch aus event_type + payload rekonstruiert —
#         WORTGLEICH zu der Formulierung, die der ursprüngliche Aufrufer von
#         `record_semantic_event` gebaut hat (Quelle je Builder als Kommentar).
#  Aufruf: python -m foreman.substrate.backfill [--batch-size N] [--limit N]
#          [--max-attempts N] [--retry-delay S] [--db-url URL] [--dry-run]
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.config import Settings, get_settings
from foreman.db.models import SemanticEvent
from foreman.ingestion.semantic import extract_substrate_ref
from foreman.logging_setup import setup_logging
from foreman.substrate.client import SubstrateClient, SubstrateError

logger = logging.getLogger("foreman.substrate.backfill")

# Marker, falls der remember zwar gelingt, die Antwort aber KEINE verwertbare
# Referenz trägt: damit bleibt der Lauf idempotent (die Zeile zählt als gespiegelt
# und wird nicht erneut gesendet), ohne eine reale Substrat-ID vorzutäuschen.
NOREF_SENTINEL = "backfilled:noref"


# ------------------------------------------------------------
#  Content-Rekonstruktion — wortgleich zu den ursprünglichen Aufrufern.
#  JEDER Builder spiegelt EINE Formulierung aus dem Produktivcode; die Quelle
#  (Datei:Zeile) steht im Kommentar. Wird dort der Text geändert, MUSS hier
#  nachgezogen werden (Test test_substrate_backfill.py pinnt die Strings).
# ------------------------------------------------------------
def _content_alarm_raised(payload: Mapping[str, Any]) -> str:
    # Quelle: ingestion/service.py (_write_alarm → _mirror, event_type="alarm_raised").
    # Harter Zugriff auf 'code' (wie die übrigen Pflichtfelder): eine Zeile OHNE den
    # Key ist defekt und wird übersprungen (KeyError → None), statt '?' zu erfinden.
    # Bei regulär erzeugten Zeilen ist 'code' immer gesetzt (ggf. None → '?').
    return (
        f"Alarm {payload['code'] or '?'} ({payload['severity']}/{payload['category']}) "
        f"an Maschine {payload['machine_id']} ausgelöst."
    )


def _content_production_run(payload: Mapping[str, Any]) -> str:
    # Quelle: ingestion/service.py (_write_production_run → _mirror, event_type="production_run").
    return (
        f"Produktionslauf {payload['product_code']} auf Linie {payload['line_id']} "
        f"gestartet ({payload['started_at']})."
    )


def _content_maintenance_performed(payload: Mapping[str, Any]) -> str:
    # Quelle: ingestion/service.py (_write_maintenance → _mirror, event_type="maintenance_performed").
    return (
        f"Wartung ({payload['type']}) an Maschine {payload['machine_id']} "
        f"durchgeführt ({payload['performed_at']})."
    )


def _content_drift_detected(payload: Mapping[str, Any]) -> str:
    # Quelle: reasoners/drift/service.py (_emit_drift_event, DRIFT_EVENT_TYPE="drift_detected").
    # Byte-genau: der Reasoner formatiert seinen Content selbst aus dem in der payload
    # gespeicherten round(effect_size, 4) (:.2f) — diese Rekonstruktion trifft ihn exakt.
    return (
        f"Verhaltens-Drift an Datenpunkt {payload['data_point_id']} erkannt "
        f"(Effektgröße {float(payload['effect_size']):.2f})."
    )


def _content_event_chain(payload: Mapping[str, Any]) -> str:
    # Quelle: reasoners/event_chain/service.py (_mirror, EVENT_CHAIN_EVENT_TYPE).
    hint = " (Hypothese)" if payload["is_hypothesis"] else ""
    return (
        f"Ereigniskette zu Alarm {payload['anchor_alarm_id']} an Maschine "
        f"{payload['machine_id']}: {payload['event_count']} Ereignisse, "
        f"Konfidenz {payload['confidence']}{hint}."
    )


def _content_failure_recommendation(payload: Mapping[str, Any]) -> str:
    # Quelle: reasoners/failure/recommendation.py (_mirror, RECOMMENDATION_EVENT_TYPE).
    return (
        f"Werker-Empfehlung zu Vorhersage {payload['prediction_id']} an Maschine "
        f"{payload['machine_id']}: Entscheidung {payload['decision']}, Horizont "
        f"{payload['horizon_h']} h (simulationsbasiert, nicht validiert)."
    )


# Registry event_type → Content-Builder. Deckt ALLE Typen ab, die je über
# record_semantic_event entstehen; der Park-Seed erzeugt nur die ersten drei.
_CONTENT_BUILDERS: dict[str, Callable[[Mapping[str, Any]], str]] = {
    "alarm_raised": _content_alarm_raised,
    "production_run": _content_production_run,
    "maintenance_performed": _content_maintenance_performed,
    "drift_detected": _content_drift_detected,
    "event_chain_reconstructed": _content_event_chain,
    "failure_recommendation": _content_failure_recommendation,
}


# Abbildung event_type → source_type. Deterministisch, kein Rückschluss: der
# event_type steht in der Zeile, die Herkunft folgt daraus eindeutig.
# `alarm`/`maintenance` sind die beiden Werte, unter denen ein Treffer auch im
# Archiv auflösbar ist (§15.9 kennt note/maintenance/alarm); die übrigen
# bezeichnen Gedächtnis-Inhalt ohne Archiv-Entsprechung.
_SOURCE_TYPES: dict[str, str] = {
    "alarm_raised": "alarm",
    "production_run": "production_run",
    "maintenance_performed": "maintenance",
    "drift_detected": "drift",
    "event_chain_reconstructed": "event_chain",
    "failure_recommendation": "failure_recommendation",
}


def herkunft_ergaenzen(event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Liefert die Metadaten für den Nachtrag: die payload plus die Herkunft.

    Seit dem 20.08.2026 schreibt der Dual-Write `source_type` und `source_id`
    selbst mit. Zeilen aus der Zeit davor — der Park-Seed und alles, was bei
    leerem Substrat entstand — tragen beides nicht.

    `source_type` wird deterministisch aus dem `event_type` ergänzt. `source_id`
    NICHT: der Schlüssel der Quellzeile steht in der Zeile nicht drin und ließe
    sich nur über Maschine plus Zeitstempel erraten. Eine falsche Zuordnung wäre
    plausibel und falsch — der Treffer bleibt dann lieber ohne Rückweg und wird
    als eigenständige Erinnerung angezeigt.

    Die DB-Zeile wird dabei NICHT verändert (Invariante: einzige Schreibung ist
    `substrate_ref`) — angereichert wird eine Kopie.
    """
    metadata = dict(payload)
    if not metadata.get("source_type"):
        abgeleitet = _SOURCE_TYPES.get(event_type)
        if abgeleitet is not None:
            metadata["source_type"] = abgeleitet
    metadata.setdefault("source_id", None)
    return metadata


def reconstruct_content(event_type: str, payload: Mapping[str, Any]) -> str | None:
    """Baut den Substrat-Text aus event_type + payload — wortgleich zum Aufrufer.

    Liefert None, wenn der event_type unbekannt ist (oder die payload ein
    erwartetes Feld nicht trägt): dann wird die Zeile übersprungen, statt einen
    erfundenen Text ins Gedächtnis zu schreiben.
    """
    builder = _CONTENT_BUILDERS.get(event_type)
    if builder is None:
        return None
    try:
        return builder(payload)
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "⏭️ payload für event_type=%s unvollständig (%s) — Zeile übersprungen.",
            event_type,
            exc,
        )
        return None


# ------------------------------------------------------------
#  Statistik
# ------------------------------------------------------------
@dataclass
class BackfillStats:
    """Zählwerk eines Backfill-Laufs."""

    scanned: int = 0  # betrachtete Zeilen
    refs_set: int = 0  # remember ok + verwertbare Referenz persistiert
    noref_marked: int = 0  # remember ok, aber keine Referenz → Marker gesetzt
    skipped_unknown: int = 0  # unbekannter event_type / unvollständige payload
    failed: int = 0  # remember nach allen Versuchen fehlgeschlagen (bleibt NULL)
    already_ref: int = 0  # defensiv: Zeile trug bereits eine Referenz
    would_remember: int = 0  # nur --dry-run: Zeilen, die gesendet WÜRDEN

    @property
    def mirrored(self) -> int:
        """Gesamtzahl tatsächlich (oder per Marker) gespiegelter Zeilen."""
        return self.refs_set + self.noref_marked

    def summary(self) -> str:
        return (
            f"scanned={self.scanned} refs_set={self.refs_set} "
            f"noref_marked={self.noref_marked} skipped_unknown={self.skipped_unknown} "
            f"failed={self.failed} already_ref={self.already_ref} "
            f"would_remember={self.would_remember}"
        )


# ------------------------------------------------------------
#  Substrat-Schnittstelle (nur das, was der Backfill braucht) + Zeilen-Sicht.
# ------------------------------------------------------------
class _SupportsRemember(Protocol):
    async def remember(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...


class _RefRow(Protocol):
    """Die Felder einer semantic_events-Zeile, die der Kern liest/schreibt."""

    id: int
    event_type: str
    payload: dict[str, Any]
    substrate_ref: str | None


# Fetcher: (after_id, limit) → bis zu `limit` NULL-ref-Zeilen mit id > after_id,
# nach id sortiert (Keyset-Pagination). Committer: persistiert den Batch.
RowFetcher = Callable[[int, int], Awaitable[Sequence[_RefRow]]]
Committer = Callable[[], Awaitable[None]]


async def _remember_with_retry(
    substrate: _SupportsRemember,
    content: str,
    metadata: dict[str, Any],
    *,
    max_attempts: int,
    base_delay_s: float,
    sleep: Callable[[float], Awaitable[None]],
    row_id: int,
) -> dict[str, Any] | None:
    """remember mit Wiederholung. Cold-Start-fest: bricht nicht beim ersten
    Timeout ab, sondern versucht es bis `max_attempts` mit linearem Backoff.
    Liefert die Antwort oder None (endgültiger Fehlschlag — Zeile bleibt NULL)."""
    last_detail = ""
    for attempt in range(1, max_attempts + 1):
        try:
            return await substrate.remember(content, metadata=metadata)
        except SubstrateError as exc:
            last_detail = str(exc)
            if attempt < max_attempts:
                logger.warning(
                    "🧠 remember Versuch %d/%d fehlgeschlagen (id=%s) — erneuter Versuch in %.1fs.",
                    attempt,
                    max_attempts,
                    row_id,
                    base_delay_s * attempt,
                )
                await sleep(base_delay_s * attempt)
    logger.error(
        "❌ remember endgültig fehlgeschlagen nach %d Versuchen (id=%s): %s — "
        "Zeile bleibt substrate_ref=NULL (Re-Run holt sie nach).",
        max_attempts,
        row_id,
        last_detail,
    )
    return None


async def _process_row(
    row: _RefRow,
    substrate: _SupportsRemember,
    *,
    stats: BackfillStats,
    max_attempts: int,
    base_delay_s: float,
    sleep: Callable[[float], Awaitable[None]],
    dry_run: bool,
    noref_sentinel: str,
) -> bool:
    """Verarbeitet EINE Zeile: rekonstruiert den Content, sendet ihn (best-effort
    mit Retry) und setzt die gewonnene Referenz. Mutiert nur row.substrate_ref.

    Liefert True, wenn row.substrate_ref gesetzt wurde (Referenz oder Marker) und
    die Zeile daher persistiert werden MUSS; sonst False (kein DB-Schreibbedarf)."""
    stats.scanned += 1
    if row.substrate_ref is not None:  # defensiv — der Fetcher liefert nur NULL-refs
        stats.already_ref += 1
        return False
    content = reconstruct_content(row.event_type, row.payload)
    if content is None:
        stats.skipped_unknown += 1
        logger.warning(
            "⏭️ event_type=%r (id=%s) nicht rekonstruierbar — übersprungen (kein Text erfunden).",
            row.event_type,
            row.id,
        )
        return False
    if dry_run:
        stats.would_remember += 1
        return False
    # metadata = die gespiegelte payload plus die deterministisch abgeleitete
    # Herkunft (Altbestand trägt sie nicht). Kopie — die DB-Zeile bleibt unberührt.
    response = await _remember_with_retry(
        substrate,
        content,
        herkunft_ergaenzen(row.event_type, row.payload),
        max_attempts=max_attempts,
        base_delay_s=base_delay_s,
        sleep=sleep,
        row_id=row.id,
    )
    if response is None:
        stats.failed += 1
        return False
    ref = extract_substrate_ref(response)
    if ref is not None:
        row.substrate_ref = ref
        stats.refs_set += 1
        logger.info("✅ gespiegelt (id=%s, event_type=%s, ref=%s).", row.id, row.event_type, ref)
    else:
        row.substrate_ref = noref_sentinel
        stats.noref_marked += 1
        logger.warning(
            "🧠 remember ok, aber keine Referenz (id=%s) — Marker %r gesetzt (Idempotenz).",
            row.id,
            noref_sentinel,
        )
    return True


async def backfill_rows(
    *,
    fetch: RowFetcher,
    commit: Committer,
    substrate: _SupportsRemember,
    batch_size: int = 50,
    max_total: int | None = None,
    max_attempts: int = 3,
    base_delay_s: float = 2.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    dry_run: bool = False,
    noref_sentinel: str = NOREF_SENTINEL,
) -> BackfillStats:
    """Entkoppelter Kern (DB-frei testbar): iteriert NULL-ref-Zeilen per
    Keyset-Pagination (`batch_size` = DB-Fetch-Seitengröße) und spiegelt jede ins
    Substrat. COMMIT erfolgt PRO erfolgreich gespiegelter Zeile, NICHT je Batch:
    so schrumpft das Duplikat-Fenster (remember ok, dann Absturz/Commit-Fehler →
    Substrat hat die Erinnerung, DB-ref aber NULL → Re-Run sendet erneut) auf
    höchstens EINE Erinnerung (das unvermeidbare Dual-Write-Restrisiko ohne
    serverseitigen Idempotenz-Key).

    Idempotenz/Terminierung: der Cursor `after_id` wandert auch über
    fehlgeschlagene/übersprungene Zeilen hinaus (sie bleiben NULL und werden erst
    von einem späteren Lauf erneut versucht) — so terminiert der Lauf immer (jeder
    nicht-leere Fetch hebt after_id) und doppelt nichts innerhalb eines Laufs."""
    stats = BackfillStats()
    after_id = 0
    processed = 0
    while max_total is None or processed < max_total:
        limit = batch_size if max_total is None else min(batch_size, max_total - processed)
        rows = await fetch(after_id, limit)
        if not rows:
            break
        for row in rows:
            if row.id > after_id:
                after_id = row.id
            mirrored = await _process_row(
                row,
                substrate,
                stats=stats,
                max_attempts=max_attempts,
                base_delay_s=base_delay_s,
                sleep=sleep,
                dry_run=dry_run,
                noref_sentinel=noref_sentinel,
            )
            processed += 1
            # Pro gesetzter Referenz sofort persistieren (Fenster ≤ 1 Erinnerung).
            if mirrored:
                await commit()
    return stats


async def referenzen_zuruecksetzen(
    session: AsyncSession,
    *,
    vor: datetime,
    dry_run: bool = False,
) -> int:
    """Setzt `substrate_ref` auf NULL für Zeilen, deren Referenz ins Leere zeigt.

    ANLASS (belegt am 20.08.2026): 65 `semantic_events` aus dem Zeitraum
    24.06. bis 13.07.2026 tragen je eine vom Substrat zurückgegebene Kennung. Keine
    davon existiert dort noch — geprüft über vier unabhängige Wege: direkter
    Schlüssel-Zugriff auf den Bestand, Aufstellung nach Herkunft, die zweite
    Instanz, und eine Suche im persönlichen Bestand. Auch nicht als gelöscht
    vermerkt; sie sind nie in der Datenbank des Substrats angekommen.

    WAS DAS FELD BEDEUTET: „Diese Zeile ist im Gedächtnis gespiegelt." Für die
    betroffenen Zeilen ist diese Aussage falsch. NULL ist damit nicht ein
    Datenverlust, sondern die Richtigstellung — und erst sie lässt den
    Backfill die Zeilen wieder aufgreifen, denn er überspringt alles mit
    gesetzter Referenz (Idempotenz-Invariante, §12.4).

    STICHTAG STATT PAUSCHAL: Zurückgesetzt wird nur, was VOR `vor` entstand.
    Alles danach ist nicht geprüft und wird nicht angefasst — ein pauschales
    Zurücksetzen würde auch gültige Referenzen entwerten und dieselbe Erinnerung
    ein zweites Mal anlegen.

    Args:
        session: DB-Sitzung.
        vor: Stichtag (`created_at <` diesem Wert). Nur geprüfte Zeiträume.
        dry_run: Nur zählen, nichts schreiben.

    Returns:
        Anzahl betroffener Zeilen.
    """
    auswahl = select(func.count()).where(
        SemanticEvent.substrate_ref.is_not(None),
        SemanticEvent.created_at < vor,
    )
    betroffen = int((await session.scalar(auswahl)) or 0)
    if dry_run or betroffen == 0:
        logger.info(
            "🔎 %d Zeile(n) mit Referenz vor %s%s.",
            betroffen,
            vor.isoformat(),
            " — Probelauf, nichts geschrieben" if dry_run else "",
        )
        return betroffen

    await session.execute(
        update(SemanticEvent)
        .where(
            SemanticEvent.substrate_ref.is_not(None),
            SemanticEvent.created_at < vor,
        )
        .values(substrate_ref=None)
    )
    await session.commit()
    logger.warning(
        "🧹 %d Referenz(en) vor %s zurückgesetzt — sie zeigten nachweislich ins Leere. "
        "Der nächste Lauf spiegelt diese Zeilen erneut.",
        betroffen,
        vor.isoformat(),
    )
    return betroffen


async def backfill_semantic_events(
    session: AsyncSession,
    substrate: _SupportsRemember,
    *,
    batch_size: int = 50,
    max_total: int | None = None,
    max_attempts: int = 3,
    base_delay_s: float = 2.0,
    dry_run: bool = False,
) -> BackfillStats:
    """DB-verdrahtete Variante: liest NULL-ref-`semantic_events` aus der Session
    und persistiert die gesetzten Referenzen je Batch (commit)."""

    async def _fetch(after_id: int, limit: int) -> Sequence[_RefRow]:
        stmt = (
            select(SemanticEvent)
            .where(SemanticEvent.substrate_ref.is_(None), SemanticEvent.id > after_id)
            .order_by(SemanticEvent.id)
            .limit(limit)
        )
        result = await session.scalars(stmt)
        return list(result.all())

    async def _commit() -> None:
        await session.commit()

    return await backfill_rows(
        fetch=_fetch,
        commit=_commit,
        substrate=substrate,
        batch_size=batch_size,
        max_total=max_total,
        max_attempts=max_attempts,
        base_delay_s=base_delay_s,
        dry_run=dry_run,
    )


# ------------------------------------------------------------
#  CLI
# ------------------------------------------------------------
def _positive_int(value: str) -> int:
    """argparse-Typ: erzwingt eine positive Ganzzahl (> 0) — fängt No-op-/Unsinn-Werte."""
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"muss eine positive Ganzzahl sein, war {value!r}")
    return ivalue


def _nonneg_float(value: str) -> float:
    """argparse-Typ: erzwingt eine nichtnegative Zahl (>= 0) — kein negativer Backoff."""
    fvalue = float(value)
    if fvalue < 0:
        raise argparse.ArgumentTypeError(f"darf nicht negativ sein, war {value!r}")
    return fvalue


def _iso_datum(value: str) -> datetime:
    """argparse-Typ: ISO-8601-Datum. Naive Angaben gelten als UTC — dieselbe
    Zeitachse, auf der `semantic_events.created_at` liegt."""
    try:
        gelesen = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"kein ISO-8601-Datum: {value!r}") from exc
    return gelesen if gelesen.tzinfo is not None else gelesen.replace(tzinfo=UTC)


def build_argparser() -> argparse.ArgumentParser:
    """Baut den CLI-Parser für den Substrat-Backfill."""
    parser = argparse.ArgumentParser(
        prog="foreman-substrate-backfill",
        description=(
            "FOREMAN Substrat-Backfill — spiegelt semantic_events mit "
            "substrate_ref IS NULL nachträglich ins Gedächtnis-Substrat (additiv, "
            "idempotent, namespace-isoliert)."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=_positive_int,
        default=50,
        help="Zeilen je DB-Fetch-Seite (Keyset-Pagination). Commit erfolgt pro Zeile.",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="Höchstzahl zu verarbeitender Zeilen (sonst alle NULL-refs).",
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=3,
        help="remember-Versuche je Zeile (Cold-Start-/Timeout-fest).",
    )
    parser.add_argument(
        "--retry-delay",
        type=_nonneg_float,
        default=2.0,
        help="Basis-Wartezeit (s) für den linearen Backoff zwischen Versuchen.",
    )
    parser.add_argument(
        "--db-url", default=None, help="Override der Datenbank-URL (sonst aus der Config)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur zählen, was gespiegelt würde — kein remember, kein DB-Schreibvorgang.",
    )
    parser.add_argument(
        "--referenzen-zuruecksetzen-vor",
        type=_iso_datum,
        default=None,
        metavar="ISO-DATUM",
        help=(
            "Setzt substrate_ref auf NULL für Zeilen VOR diesem Datum, sodass der Lauf "
            "sie erneut spiegelt. NUR verwenden, wenn nachgewiesen ist, dass die "
            "Referenzen dieses Zeitraums ins Leere zeigen — sonst entsteht die "
            "Erinnerung ein zweites Mal. Beachtet --dry-run."
        ),
    )
    return parser


async def amain(argv: list[str] | None = None, *, settings: Settings | None = None) -> int:
    """Async-Entrypoint: parst Argumente, baut Engine/Session und fährt den Backfill."""
    args = build_argparser().parse_args(argv)
    cfg = settings or get_settings()
    database_url = args.db_url or cfg.database_url
    # Fail-closed: ohne konfiguriertes Substrat gibt es nichts zu spiegeln.
    substrate = SubstrateClient.from_settings(cfg)

    engine = create_async_engine(database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with maker() as session:
            logger.info(
                "🔄 Starte Substrat-Backfill (namespace=%s, batch=%s, limit=%s, dry_run=%s).",
                cfg.substrate_namespace,
                args.batch_size,
                args.limit,
                args.dry_run,
            )
            if args.referenzen_zuruecksetzen_vor is not None:
                await referenzen_zuruecksetzen(
                    session,
                    vor=args.referenzen_zuruecksetzen_vor,
                    dry_run=args.dry_run,
                )
            stats = await backfill_semantic_events(
                session,
                substrate,
                batch_size=args.batch_size,
                max_total=args.limit,
                max_attempts=args.max_attempts,
                base_delay_s=args.retry_delay,
                dry_run=args.dry_run,
            )
            logger.info("✅ Backfill fertig: %s", stats.summary())
    finally:
        await engine.dispose()
        await substrate.aclose()
    return 0


def main() -> None:  # pragma: no cover — dünner Sync-Wrapper um amain
    """Synchroner Konsolen-Entrypoint (python -m foreman.substrate.backfill)."""
    setup_logging()
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":  # pragma: no cover
    main()
