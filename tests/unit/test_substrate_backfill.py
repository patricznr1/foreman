# ============================================================
#  FOREMAN — tests/unit/test_substrate_backfill.py
#  Zweck: DB-freier Unit-Test des Substrat-Backfills (substrate/backfill.py).
#  Deckt: Content-Rekonstruktion (wortgleich, je event_type, fehlende Felder),
#         nur-NULL-refs, Referenz-Update, Idempotenz, Keyset-Pagination über
#         mehrere Batches (auch mit dauerhaft scheiternden/übersprungenen Zeilen,
#         die NULL bleiben → echter Cursor-Test), per-Zeile-Commit, Cold-Start-
#         Retry x Pagination, endgültiger Fehlschlag, No-Ref-Marker, ref-Form-
#         Varianten, --dry-run, --limit, CLI-Parser.
#  Der Kern (backfill_rows) ist über injizierten Fetcher/Committer von der DB
#  entkoppelt; der Fake-Fetcher spiegelt die echte SQL (NULL-ref + id>cursor +
#  order by id + limit). Kein Substrat, keine DB nötig.
# ============================================================
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import pytest

from foreman.substrate.backfill import (
    NOREF_SENTINEL,
    BackfillStats,
    backfill_rows,
    build_argparser,
    reconstruct_content,
)
from foreman.substrate.client import SubstrateError


# ------------------------------------------------------------
#  Test-Doppel
# ------------------------------------------------------------
@dataclass
class FakeRow:
    """Minimaler semantic_events-Zeilen-Stand-in (erfüllt das _RefRow-Protokoll)."""

    id: int
    event_type: str
    payload: dict[str, Any]
    substrate_ref: str | None = None


class OkSubstrate:
    """Erreichbar — liefert eine verwertbare Referenz je remember."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def remember(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls.append((content, metadata))
        return {"id": f"ref-{len(self.calls)}"}


class SelectiveSubstrate:
    """Wirft genau für remember, deren metadata['machine_id'] in fail_ids liegt."""

    def __init__(self, fail_ids: Iterable[int]) -> None:
        self.fail_ids = set(fail_ids)
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def remember(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls.append((content, metadata))
        machine_id = (metadata or {}).get("machine_id")
        if machine_id in self.fail_ids:
            raise SubstrateError(f"Test-Fehler für machine_id={machine_id}")
        return {"id": f"ref-{len(self.calls)}"}


class MemoryIdSubstrate:
    """Liefert die Referenz unter dem Schlüssel 'memory_id' (andere ref-Form)."""

    async def remember(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {"memory_id": "m-1"}


class EmptyRefSubstrate:
    """Erreichbar, aber Referenz ist leerer String → gilt als keine Referenz."""

    def __init__(self) -> None:
        self.calls = 0

    async def remember(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls += 1
        return {"id": ""}


class NoRefSubstrate:
    """Erreichbar, aber Antwort ohne verwertbare Referenz."""

    def __init__(self) -> None:
        self.calls = 0

    async def remember(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls += 1
        return {"status": "ok"}


class FailSubstrate:
    """Wirft immer — simuliert dauerhaften Substrat-Ausfall."""

    def __init__(self) -> None:
        self.calls = 0

    async def remember(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls += 1
        raise SubstrateError("Substrat nicht erreichbar (Test)")


class ColdStartSubstrate:
    """Wirft die ersten `fail_times` Male (Cold-Start/Timeout), dann erfolgreich."""

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    async def remember(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise SubstrateError("Cold-Start-Timeout (Test)")
        return {"id": f"warm-{self.calls}"}


@dataclass
class FakeDb:
    """In-Memory-Ersatz für Fetch (echte SQL nachgebildet) + Commit-/Limit-Zähler."""

    rows: list[FakeRow]
    commits: int = field(default=0)
    fetch_limits: list[int] = field(default_factory=list)

    async def fetch(self, after_id: int, limit: int) -> list[FakeRow]:
        self.fetch_limits.append(limit)
        pending = sorted(
            (r for r in self.rows if r.substrate_ref is None and r.id > after_id),
            key=lambda r: r.id,
        )
        return pending[:limit]

    async def commit(self) -> None:
        self.commits += 1


async def _no_sleep(_seconds: float) -> None:
    """Backoff ohne echte Wartezeit (Tests bleiben schnell)."""
    return None


def _maint_row(machine_id: int) -> FakeRow:
    return FakeRow(
        machine_id,
        "maintenance_performed",
        {
            "type": "inspection",
            "machine_id": machine_id,
            "component_id": None,
            "performed_at": "2026-06-01T00:00:00+00:00",
            "performed_by": None,
        },
    )


def _maint_rows(n: int) -> list[FakeRow]:
    return [_maint_row(i) for i in range(1, n + 1)]


def _park_rows() -> list[FakeRow]:
    return [
        FakeRow(
            1,
            "alarm_raised",
            {
                "code": "E1",
                "severity": "alarm",
                "category": "hardware",
                "machine_id": 1,
                "raised_at": "2026-06-01T00:00:00+00:00",
            },
        ),
        FakeRow(
            2,
            "production_run",
            {
                "product_code": "P-1",
                "order_id": None,
                "line_id": 1,
                "started_at": "2026-06-01T00:00:00+00:00",
                "ended_at": None,
            },
        ),
        _maint_row(3),
    ]


# ------------------------------------------------------------
#  Content-Rekonstruktion — wortgleich (gepinnt gegen Drift der Aufrufer)
# ------------------------------------------------------------
def test_reconstruct_alarm_raised() -> None:
    payload = {
        "code": "E42",
        "severity": "critical",
        "category": "hardware",
        "machine_id": 7,
        "raised_at": "2026-06-01T10:00:00+00:00",
    }
    assert (
        reconstruct_content("alarm_raised", payload)
        == "Alarm E42 (critical/hardware) an Maschine 7 ausgelöst."
    )


def test_reconstruct_alarm_raised_ohne_code() -> None:
    payload = {
        "code": None,
        "severity": "warning",
        "category": "process",
        "machine_id": 3,
        "raised_at": "2026-06-01T10:00:00+00:00",
    }
    assert (
        reconstruct_content("alarm_raised", payload)
        == "Alarm ? (warning/process) an Maschine 3 ausgelöst."
    )


def test_reconstruct_production_run() -> None:
    payload = {
        "product_code": "WID-9",
        "order_id": "O-1",
        "line_id": 2,
        "started_at": "2026-06-01T08:00:00+00:00",
        "ended_at": None,
    }
    assert (
        reconstruct_content("production_run", payload)
        == "Produktionslauf WID-9 auf Linie 2 gestartet (2026-06-01T08:00:00+00:00)."
    )


def test_reconstruct_maintenance_performed() -> None:
    payload = {
        "type": "lubrication",
        "machine_id": 5,
        "component_id": 11,
        "performed_at": "2026-06-02T06:30:00+00:00",
        "performed_by": "v1:" + "ab" * 32,
    }
    assert (
        reconstruct_content("maintenance_performed", payload)
        == "Wartung (lubrication) an Maschine 5 durchgeführt (2026-06-02T06:30:00+00:00)."
    )


def test_reconstruct_drift_detected() -> None:
    payload = {
        "reasoner": "drift",
        "machine_id": 4,
        "data_point_id": 99,
        "detected_at": "2026-06-03T12:00:00+00:00",
        "effect_size": 3.1416,
    }
    assert (
        reconstruct_content("drift_detected", payload)
        == "Verhaltens-Drift an Datenpunkt 99 erkannt (Effektgröße 3.14)."
    )


def test_reconstruct_event_chain_mit_und_ohne_hypothese() -> None:
    base = {
        "reasoner": "event_chain",
        "anchor_alarm_id": 12,
        "machine_id": 6,
        "event_count": 4,
        "confidence": "hoch",
        "referenced_source_ids": ["a"],
        "flagged_unsupported": [],
    }
    assert reconstruct_content("event_chain_reconstructed", {**base, "is_hypothesis": False}) == (
        "Ereigniskette zu Alarm 12 an Maschine 6: 4 Ereignisse, Konfidenz hoch."
    )
    assert reconstruct_content("event_chain_reconstructed", {**base, "is_hypothesis": True}) == (
        "Ereigniskette zu Alarm 12 an Maschine 6: 4 Ereignisse, Konfidenz hoch (Hypothese)."
    )


def test_reconstruct_failure_recommendation() -> None:
    payload = {
        "reasoner": "failure_recommendation",
        "prediction_id": 21,
        "machine_id": 8,
        "decision": "elevated_risk",
        "horizon_h": 48,
        "referenced_source_ids": [],
        "validation_status": "simulation_only",
        "data_regime": "simulation",
    }
    assert reconstruct_content("failure_recommendation", payload) == (
        "Werker-Empfehlung zu Vorhersage 21 an Maschine 8: Entscheidung elevated_risk, "
        "Horizont 48 h (simulationsbasiert, nicht validiert)."
    )


def test_reconstruct_unbekannter_typ_ist_none() -> None:
    assert reconstruct_content("mystery_event", {"x": 1}) is None


@pytest.mark.parametrize(
    ("event_type", "payload"),
    [
        ("alarm_raised", {"severity": "warning"}),  # ohne code/category/machine_id
        ("alarm_raised", {"code": "E1", "category": "p", "machine_id": 1}),  # ohne severity
        ("production_run", {"product_code": "P"}),  # ohne line_id/started_at
        ("maintenance_performed", {"type": "x"}),  # ohne machine_id/performed_at
        ("drift_detected", {"data_point_id": 1}),  # ohne effect_size
        ("event_chain_reconstructed", {"anchor_alarm_id": 1, "machine_id": 1}),  # ohne is_hyp
        ("failure_recommendation", {"prediction_id": 1, "machine_id": 1}),  # ohne decision
    ],
)
def test_reconstruct_unvollstaendige_payload_ist_none(
    event_type: str, payload: dict[str, Any]
) -> None:
    # Kein Builder darf bei fehlendem Pflichtfeld crashen — er liefert None (Skip).
    assert reconstruct_content(event_type, payload) is None


# ------------------------------------------------------------
#  Kern: backfill_rows — Grundpfade
# ------------------------------------------------------------
async def test_backfill_setzt_refs_und_spiegelt_payload() -> None:
    db = FakeDb(_park_rows())
    sub = OkSubstrate()
    stats = await backfill_rows(fetch=db.fetch, commit=db.commit, substrate=sub, sleep=_no_sleep)

    assert stats.scanned == 3
    assert stats.refs_set == 3
    assert stats.mirrored == 3
    assert all(r.substrate_ref is not None for r in db.rows)
    assert len(sub.calls) == 3
    assert db.commits == 3  # per-Zeile-Commit
    # metadata == die jeweilige payload (exakt wie der ursprüngliche Dual-Write).
    for r, (_content, meta) in zip(db.rows, sub.calls, strict=True):
        assert meta == r.payload


async def test_backfill_nur_null_refs() -> None:
    rows = _park_rows()
    rows[1].substrate_ref = "schon-da"  # bereits gespiegelt → unangetastet
    db = FakeDb(rows)
    sub = OkSubstrate()
    stats = await backfill_rows(fetch=db.fetch, commit=db.commit, substrate=sub, sleep=_no_sleep)

    assert len(sub.calls) == 2  # nur die zwei NULL-ref-Zeilen
    assert stats.scanned == 2
    assert stats.refs_set == 2
    assert rows[1].substrate_ref == "schon-da"  # nicht überschrieben


async def test_backfill_idempotenz_zweiter_lauf_macht_nichts() -> None:
    db = FakeDb(_park_rows())
    sub = OkSubstrate()
    await backfill_rows(fetch=db.fetch, commit=db.commit, substrate=sub, sleep=_no_sleep)
    assert len(sub.calls) == 3

    stats2 = await backfill_rows(fetch=db.fetch, commit=db.commit, substrate=sub, sleep=_no_sleep)
    assert stats2.scanned == 0  # nichts mehr NULL → nichts zu tun
    assert len(sub.calls) == 3  # keine weiteren remember-Aufrufe


async def test_backfill_leere_db() -> None:
    db = FakeDb([])
    sub = OkSubstrate()
    stats = await backfill_rows(fetch=db.fetch, commit=db.commit, substrate=sub, sleep=_no_sleep)
    assert stats.scanned == 0
    assert len(sub.calls) == 0
    assert db.commits == 0  # leerer Fetch bricht vor jedem Commit ab


# ------------------------------------------------------------
#  Keyset-Pagination — Cursor-Korrektheit über mehrere Batches
# ------------------------------------------------------------
async def test_backfill_pagination_verarbeitet_alle_seiten() -> None:
    db = FakeDb(_maint_rows(5))
    sub = OkSubstrate()
    stats = await backfill_rows(
        fetch=db.fetch, commit=db.commit, substrate=sub, batch_size=2, sleep=_no_sleep
    )
    assert stats.refs_set == 5
    assert len(sub.calls) == 5
    assert db.commits == 5  # per-Zeile-Commit (nicht je Batch)


async def test_backfill_cursor_terminiert_bei_durchgehendem_fehlschlag() -> None:
    # ECHTER Cursor-Test: alle remember scheitern → Zeilen bleiben NULL. Allein
    # after_id darf die Terminierung leisten (sonst würde fetch ewig dieselben
    # NULL-Zeilen liefern → Endlosschleife). max_attempts=1 → kein Retry.
    db = FakeDb(_maint_rows(5))
    sub = FailSubstrate()
    stats = await backfill_rows(
        fetch=db.fetch,
        commit=db.commit,
        substrate=sub,
        batch_size=2,
        max_attempts=1,
        sleep=_no_sleep,
    )
    assert stats.scanned == 5
    assert stats.failed == 5
    assert sub.calls == 5
    assert db.commits == 0  # nichts gesetzt → nichts committet
    assert all(r.substrate_ref is None for r in db.rows)


async def test_backfill_alle_scheitern_mit_retry_ueber_mehrere_batches() -> None:
    db = FakeDb(_maint_rows(5))
    sub = FailSubstrate()
    stats = await backfill_rows(
        fetch=db.fetch,
        commit=db.commit,
        substrate=sub,
        batch_size=2,
        max_attempts=2,
        base_delay_s=0.0,
        sleep=_no_sleep,
    )
    assert stats.failed == 5
    assert sub.calls == 10  # 5 Zeilen x 2 Versuche
    assert db.commits == 0
    assert all(r.substrate_ref is None for r in db.rows)


async def test_backfill_gemischt_fehlschlag_ueber_batchgrenze() -> None:
    # machine_id=3 scheitert dauerhaft; die übrigen werden gespiegelt. Der Cursor
    # muss über die gescheiterte Zeile hinauswandern (sie bleibt NULL).
    db = FakeDb(_maint_rows(5))
    sub = SelectiveSubstrate(fail_ids={3})
    stats = await backfill_rows(
        fetch=db.fetch,
        commit=db.commit,
        substrate=sub,
        batch_size=2,
        max_attempts=1,
        sleep=_no_sleep,
    )
    assert stats.scanned == 5
    assert stats.refs_set == 4
    assert stats.failed == 1
    by_id = {r.id: r for r in db.rows}
    assert by_id[3].substrate_ref is None  # gescheitert → NULL
    assert all(by_id[i].substrate_ref is not None for i in (1, 2, 4, 5))
    assert db.commits == 4  # nur die 4 erfolgreichen


async def test_backfill_grosse_menge_reihenfolge_ohne_dublette_oder_luecke() -> None:
    db = FakeDb(_maint_rows(25))
    sub = OkSubstrate()
    stats = await backfill_rows(
        fetch=db.fetch, commit=db.commit, substrate=sub, batch_size=10, sleep=_no_sleep
    )
    assert stats.refs_set == 25
    assert len(sub.calls) == 25
    sent_ids = [meta["machine_id"] for _content, meta in sub.calls if meta is not None]
    assert sent_ids == sorted(set(sent_ids))  # jede id genau einmal, in Reihenfolge
    assert sent_ids == list(range(1, 26))


# ------------------------------------------------------------
#  Cold-Start-Retry x Pagination
# ------------------------------------------------------------
async def test_backfill_cold_start_retry_dann_ok() -> None:
    db = FakeDb([_maint_row(1)])
    sub = ColdStartSubstrate(fail_times=1)  # erster Versuch kalt, zweiter warm
    stats = await backfill_rows(
        fetch=db.fetch,
        commit=db.commit,
        substrate=sub,
        max_attempts=3,
        base_delay_s=0.0,
        sleep=_no_sleep,
    )
    assert sub.calls == 2  # ein Retry
    assert stats.refs_set == 1
    assert db.rows[0].substrate_ref == "warm-2"


async def test_backfill_cold_start_dann_rest_laeuft_normal_weiter() -> None:
    # Erster Substrat-Call kalt (1 Timeout), danach warm — die übrigen Zeilen
    # über die Batch-Grenze hinweg laufen normal durch.
    db = FakeDb(_maint_rows(3))
    sub = ColdStartSubstrate(fail_times=1)
    stats = await backfill_rows(
        fetch=db.fetch,
        commit=db.commit,
        substrate=sub,
        batch_size=2,
        max_attempts=3,
        base_delay_s=0.0,
        sleep=_no_sleep,
    )
    assert stats.refs_set == 3
    assert sub.calls == 4  # 2 für Zeile1 (1 kalt + 1 warm) + je 1 für Zeile2/3
    assert all(r.substrate_ref is not None for r in db.rows)


async def test_backfill_erschoepfter_retry_stoppt_rest_nicht() -> None:
    # Zeile 1 schöpft den Retry aus (failed), Zeilen 2/3 werden trotzdem gespiegelt.
    db = FakeDb(_maint_rows(3))
    sub = SelectiveSubstrate(fail_ids={1})
    stats = await backfill_rows(
        fetch=db.fetch,
        commit=db.commit,
        substrate=sub,
        batch_size=2,
        max_attempts=2,
        base_delay_s=0.0,
        sleep=_no_sleep,
    )
    assert stats.failed == 1
    assert stats.refs_set == 2
    by_id = {r.id: r for r in db.rows}
    assert by_id[1].substrate_ref is None
    assert by_id[2].substrate_ref is not None
    assert by_id[3].substrate_ref is not None


# ------------------------------------------------------------
#  Endgültiger Fehlschlag / unbekannte Typen / ref-Formen
# ------------------------------------------------------------
async def test_backfill_endgueltiger_fehlschlag_bleibt_null() -> None:
    db = FakeDb([_maint_row(1)])
    sub = FailSubstrate()
    stats = await backfill_rows(
        fetch=db.fetch,
        commit=db.commit,
        substrate=sub,
        max_attempts=3,
        base_delay_s=0.0,
        sleep=_no_sleep,
    )
    assert sub.calls == 3  # alle Versuche ausgeschöpft
    assert stats.failed == 1
    assert stats.refs_set == 0
    assert db.rows[0].substrate_ref is None  # bleibt NULL → Re-Run holt nach


async def test_backfill_unbekannter_typ_wird_uebersprungen() -> None:
    db = FakeDb([FakeRow(1, "mystery_event", {"x": 1})])
    sub = OkSubstrate()
    stats = await backfill_rows(fetch=db.fetch, commit=db.commit, substrate=sub, sleep=_no_sleep)
    assert stats.skipped_unknown == 1
    assert len(sub.calls) == 0
    assert db.rows[0].substrate_ref is None


async def test_backfill_unbekannter_typ_zwischen_gueltigen() -> None:
    rows = [_park_rows()[0], FakeRow(2, "mystery_event", {"x": 1}), _maint_row(3)]
    db = FakeDb(rows)
    sub = OkSubstrate()
    stats = await backfill_rows(
        fetch=db.fetch, commit=db.commit, substrate=sub, batch_size=2, sleep=_no_sleep
    )
    assert stats.refs_set == 2
    assert stats.skipped_unknown == 1
    assert len(sub.calls) == 2
    assert rows[1].substrate_ref is None  # mystery bleibt NULL
    assert rows[0].substrate_ref is not None and rows[2].substrate_ref is not None


async def test_backfill_noref_marker_bei_fehlender_referenz() -> None:
    db = FakeDb([_maint_row(1)])
    sub = NoRefSubstrate()
    stats = await backfill_rows(fetch=db.fetch, commit=db.commit, substrate=sub, sleep=_no_sleep)
    assert stats.noref_marked == 1
    assert stats.refs_set == 0
    assert db.rows[0].substrate_ref == NOREF_SENTINEL  # idempotent trotz fehlender ID
    assert db.commits == 1  # Marker wird persistiert


async def test_backfill_ref_unter_memory_id_schluessel() -> None:
    db = FakeDb([_maint_row(1)])
    stats = await backfill_rows(
        fetch=db.fetch, commit=db.commit, substrate=MemoryIdSubstrate(), sleep=_no_sleep
    )
    assert stats.refs_set == 1
    assert db.rows[0].substrate_ref == "m-1"


async def test_backfill_leere_ref_gilt_als_keine_ref() -> None:
    db = FakeDb([_maint_row(1)])
    stats = await backfill_rows(
        fetch=db.fetch, commit=db.commit, substrate=EmptyRefSubstrate(), sleep=_no_sleep
    )
    assert stats.noref_marked == 1
    assert db.rows[0].substrate_ref == NOREF_SENTINEL


async def test_backfill_defensiv_ueberspringt_bereits_referenzierte_zeile() -> None:
    # Defensiv: liefert ein Fetcher (entgegen der echten SQL) eine bereits
    # referenzierte Zeile, überspringt der Kern sie ohne remember.
    row = FakeRow(1, "maintenance_performed", {"type": "x"}, substrate_ref="da")
    served = {"done": False}

    async def one_shot_fetch(after_id: int, limit: int) -> list[FakeRow]:
        if served["done"]:
            return []
        served["done"] = True
        return [row]

    async def noop_commit() -> None:
        return None

    sub = OkSubstrate()
    stats = await backfill_rows(
        fetch=one_shot_fetch, commit=noop_commit, substrate=sub, sleep=_no_sleep
    )
    assert stats.already_ref == 1
    assert len(sub.calls) == 0
    assert row.substrate_ref == "da"


# ------------------------------------------------------------
#  --dry-run und --limit
# ------------------------------------------------------------
async def test_backfill_dry_run_schreibt_nicht() -> None:
    db = FakeDb(_park_rows())
    sub = OkSubstrate()
    stats = await backfill_rows(
        fetch=db.fetch, commit=db.commit, substrate=sub, dry_run=True, sleep=_no_sleep
    )
    assert stats.would_remember == 3
    assert len(sub.calls) == 0  # kein remember
    assert db.commits == 0  # kein Commit
    assert all(r.substrate_ref is None for r in db.rows)  # nichts geschrieben


async def test_backfill_dry_run_zaehlt_unbekannte_nicht_als_would_remember() -> None:
    rows = [_park_rows()[0], FakeRow(2, "mystery_event", {"x": 1}), _maint_row(3)]
    db = FakeDb(rows)
    sub = OkSubstrate()
    stats = await backfill_rows(
        fetch=db.fetch, commit=db.commit, substrate=sub, dry_run=True, sleep=_no_sleep
    )
    assert stats.would_remember == 2
    assert stats.skipped_unknown == 1
    assert len(sub.calls) == 0


async def test_backfill_limit_begrenzt_verarbeitung_und_fetch() -> None:
    db = FakeDb(_park_rows())
    sub = OkSubstrate()
    stats = await backfill_rows(
        fetch=db.fetch, commit=db.commit, substrate=sub, max_total=2, sleep=_no_sleep
    )
    assert stats.scanned == 2
    assert len(sub.calls) == 2
    # limit wird auch an den Fetcher durchgereicht (min(batch_size, rest)).
    assert db.fetch_limits[0] == 2


async def test_backfill_limit_groesser_als_gesamtzahl() -> None:
    db = FakeDb(_park_rows())
    sub = OkSubstrate()
    stats = await backfill_rows(
        fetch=db.fetch, commit=db.commit, substrate=sub, max_total=99, sleep=_no_sleep
    )
    assert stats.scanned == 3  # terminiert sauber bei Erschöpfung der Zeilen


def test_backfill_stats_summary_enthaelt_zaehler() -> None:
    stats = BackfillStats(scanned=3, refs_set=2, noref_marked=1)
    summary = stats.summary()
    assert "scanned=3" in summary
    assert "refs_set=2" in summary
    assert stats.mirrored == 3


# ------------------------------------------------------------
#  CLI-Parser
# ------------------------------------------------------------
def test_argparser_defaults() -> None:
    args = build_argparser().parse_args([])
    assert args.batch_size == 50
    assert args.limit is None
    assert args.max_attempts == 3
    assert args.retry_delay == pytest.approx(2.0)
    assert args.dry_run is False


def test_argparser_flags() -> None:
    args = build_argparser().parse_args(
        ["--batch-size", "10", "--limit", "5", "--max-attempts", "7", "--dry-run"]
    )
    assert args.batch_size == 10
    assert args.limit == 5
    assert args.max_attempts == 7
    assert args.dry_run is True


@pytest.mark.parametrize(
    "argv",
    [
        ["--batch-size", "0"],  # No-op-Lauf
        ["--batch-size", "-1"],
        ["--limit", "0"],
        ["--max-attempts", "0"],  # überspränge remember komplett
        ["--retry-delay", "-1"],  # negativer Backoff
        ["--batch-size", "abc"],  # nicht-numerisch
    ],
)
def test_argparser_lehnt_ungueltige_werte_ab(argv: list[str]) -> None:
    # argparse beendet bei Typ-/Wertfehler mit SystemExit(2) — kein No-op/Unsinn-Lauf.
    with pytest.raises(SystemExit):
        build_argparser().parse_args(argv)
