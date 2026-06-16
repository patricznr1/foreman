# ============================================================
#  FOREMAN — realtime/hub.py
#  Zweck: Der In-Process-WS-Hub (F5) EINES Workers. Hält je Thema die Abonnenten
#         und coalesct eingehende Änderungs-Signale serverseitig per debounce zu
#         EINEM Signal pro Thema und Fenster (Vorgabe 4: debounce → danach lädt
#         der Endpoint scope-korrekt nach). `broad` (z. B. nach LISTEN-Reconnect)
#         markiert alle abonnierten Themen frisch — Snapshot-Reload statt Lücke.
#  Architektur-Einordnung: Live-Push-Layer (F5), Consumer-Seite, PRO Worker (kein
#         globaler Singleton — jeder Worker hat seinen eigenen Hub + Listener und
#         bedient seine eigenen Clients). Der Hub trägt NUR Routing + debounce;
#         das Laden der Sicht (scope-abhängig) macht der WS-Endpoint, damit der Hub
#         transport- und DB-frei bleibt (testbar ohne beides).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from foreman.realtime.channels import ChangeSet
from foreman.realtime.topics import topics_for_change

# Default-Debounce-Fenster (Sekunden) — die serverseitige Drossel pro Hub.
DEFAULT_DEBOUNCE_SECONDS = 0.1


@dataclass(eq=False)
class Subscription:
    """Ein verbundener WS-Client: eine Queue „schmutziger" Themen + seine Abos.

    `eq=False`: Abos sind identitätsbasiert (jede Verbindung ist eindeutig) — so
    bleibt die Subscription hashbar und kann in den Themen-Mengen liegen.

    Der Endpoint liest `next_dirty()` und lädt dann das Thema scope-korrekt nach.
    `_queued` dedupliziert, sodass ein langsamer/leerlaufender Client die Queue
    nicht aufstaut (pro Thema höchstens ein offenes Signal).
    """

    queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    topics: set[str] = field(default_factory=set)
    _queued: set[str] = field(default_factory=set, init=False, repr=False)

    def mark_dirty(self, topic: str) -> None:
        """Signalisiert dem Client, dass `topic` neu zu laden ist (dedupliziert)."""
        if topic not in self._queued:
            self._queued.add(topic)
            self.queue.put_nowait(topic)

    async def next_dirty(self) -> str:
        """Wartet auf das nächste schmutzige Thema (für die Endpoint-Schleife)."""
        topic = await self.queue.get()
        self._queued.discard(topic)
        return topic


class DashboardHub:
    """Themen-Router + Debouncer eines Workers — füttert die WS-Abonnenten."""

    def __init__(self, *, debounce_seconds: float = DEFAULT_DEBOUNCE_SECONDS) -> None:
        self._subscribers: dict[str, set[Subscription]] = {}
        self._pending: set[str] = set()
        self._pending_broad = False
        self._debounce_seconds = debounce_seconds
        self._flush_handle: asyncio.TimerHandle | None = None

    def register(self) -> Subscription:
        """Legt eine neue (noch themenlose) Abo-Verbindung an."""
        return Subscription()

    def subscribe(self, subscription: Subscription, topic: str) -> None:
        """Hängt eine Verbindung an ein Thema (nach erfolgter Autorisierung)."""
        self._subscribers.setdefault(topic, set()).add(subscription)
        subscription.topics.add(topic)

    def unsubscribe(self, subscription: Subscription, topic: str) -> None:
        """Löst eine Verbindung von einem Thema (räumt leere Themen auf)."""
        subscribers = self._subscribers.get(topic)
        if subscribers is not None:
            subscribers.discard(subscription)
            if not subscribers:
                del self._subscribers[topic]
        subscription.topics.discard(topic)

    def remove(self, subscription: Subscription) -> None:
        """Trennt eine Verbindung von allen Themen (Disconnect)."""
        for topic in list(subscription.topics):
            self.unsubscribe(subscription, topic)

    def dispatch(self, change: ChangeSet) -> None:
        """Nimmt ein ChangeSet (aus dem NOTIFY) auf und plant das Flushen.

        Sammelt die betroffenen Themen und debounct sie — mehrere Changes im
        selben Fenster ergeben EIN Signal pro Thema (Vorgabe 4).
        """
        if change.is_empty():
            return
        if change.broad:
            self._pending_broad = True
        else:
            self._pending |= topics_for_change(change)
        self._schedule_flush()

    def _schedule_flush(self) -> None:
        if self._flush_handle is None:
            loop = asyncio.get_running_loop()
            self._flush_handle = loop.call_later(self._debounce_seconds, self._flush)

    def _flush(self) -> None:
        self._flush_handle = None
        if self._pending_broad:
            # Breites Refresh (Reconnect/Overflow): alle abonnierten Themen frisch.
            dirty: set[str] = set(self._subscribers.keys())
            self._pending_broad = False
            self._pending.clear()
        else:
            dirty = self._pending
            self._pending = set()
        for topic in dirty:
            for subscription in self._subscribers.get(topic, set()):
                subscription.mark_dirty(topic)
