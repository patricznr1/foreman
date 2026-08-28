# ============================================================
#  FOREMAN — substrate/client.py
#  Zweck: Dünner HTTP-Wrapper für das Gedächtnis-Substrat (NEXUS).
#  Architektur-Einordnung: Brücke Schicht 2 → externer Dienst (GROUND_TRUTH §9).
#  Vertrag: generischer REST über httpx.AsyncClient, Bearer-Token-Auth,
#         JSON-Payloads. Endpunkt-Pfade konfigurierbar (config.substrate_*_path),
#         sodass FOREMAN an die reale NEXUS-API angebunden werden kann, ohne
#         Substrat-Engine-Interna im Repo zu hinterlegen.
#  Methoden = HTTP-Operationen des Dienstes: remember / recall / reason /
#         drift_status / reflect.
# ============================================================
from __future__ import annotations

from typing import Any

import httpx

from foreman.config import Settings


class SubstrateNotConfiguredError(RuntimeError):
    """Substrat-Anbindung ist nicht konfiguriert (SUBSTRATE_BASE_URL fehlt)."""


class SubstrateError(RuntimeError):
    """Fehler bei der Kommunikation mit dem Gedächtnis-Substrat (Deutsch, §6)."""


class SubstrateNotFoundError(SubstrateError):
    """Unter dieser Kennung liegt im angefragten Bereich nichts.

    Eine UNTERART von `SubstrateError`, damit bestehende Aufrufer, die nur die
    Oberklasse fangen, unverändert weiterlaufen. Wer den Unterschied braucht,
    fängt sie gezielt — beim Löschen etwa trennt sie „ist schon weg" von „der
    Weg ist gestört". Das eine ist das erreichte Ziel, das andere ein noch
    ausstehender Versuch; sie gleich zu behandeln hiesse, eine Zeile entweder
    dauerhaft im Kreis zu drehen oder vorschnell abzuhaken.
    """


class SubstrateClient:
    """HTTP-Client für das Gedächtnis-Substrat.

    Base-URL + Token kommen aus der Config (.env). Ein bereits gebauter
    `httpx.AsyncClient` kann injiziert werden (Tests gegen Mock-Transport).
    """

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None = None,
        timeout_s: float = 10.0,
        namespace: str = "foreman",
        paths: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._namespace = namespace
        self._paths = paths or {
            "remember": "/remember",
            "recall": "/recall",
            "reason": "/reason",
            "drift_status": "/drift_status",
            "reflect": "/reflect",
            # Löschen adressiert einen EINZELNEN Eintrag: der Pfad bekommt die
            # Kennung angehängt, anders als die POST-Wege oben.
            "forget": "",
        }
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            self._client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout_s)
            self._owns_client = True

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        namespace: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> SubstrateClient:
        """Baut den Client aus der Config. Wirft, wenn keine Base-URL gesetzt ist.

        `namespace` überschreibt den Betriebs-Namespace — genutzt vom Round-Trip-Smoke,
        der seine Test-Erinnerungen bewusst NICHT dort ablegt, wo abgerufen wird.
        """
        if not settings.substrate_base_url:
            raise SubstrateNotConfiguredError(
                "SUBSTRATE_BASE_URL ist nicht gesetzt — Substrat-Anbindung fehlt."
            )
        # EINE Quelle für den Bereich: derselbe aufgelöste Wert geht in den
        # Klienten UND in den Löschpfad. Getrennt gepflegt könnten sie
        # auseinanderlaufen — ein Klient mit abweichendem Bereich (der
        # Round-Trip-Smoke setzt einen) schriebe in den einen und löschte im
        # anderen. Die Falle ist heute gestellt, nicht ausgelöst: Der Smoke ruft
        # `forget` nicht auf.
        ns = namespace or settings.substrate_namespace
        return cls(
            base_url=settings.substrate_base_url,
            # SecretStr → Klartext erst hier, unmittelbar vor dem Header-Bau (§8).
            token=(
                settings.substrate_token.get_secret_value() if settings.substrate_token else None
            ),
            timeout_s=settings.substrate_timeout_s,
            namespace=ns,
            paths={
                "remember": settings.substrate_remember_path,
                "recall": settings.substrate_recall_path,
                "reason": settings.substrate_reason_path,
                "drift_status": settings.substrate_drift_status_path,
                "reflect": settings.substrate_reflect_path,
                # MUSS hier stehen: Ein übergebenes `paths` ERSETZT den
                # Vorgabewert im Konstruktor vollständig. Fehlt der Eintrag,
                # wirft `forget` einen KeyError — und zwar nur im Betrieb, weil
                # ein von Hand gebauter Klient den Vorgabewert behält. Genau so
                # blieb der Löschweg unbemerkt unerreichbar (Befund 25.08.2026).
                #
                # Der Bereich wird HIER angehängt, nicht in der Einstellung: Die
                # Gegenstelle adressiert /{bereich}/{kennung}, und `forget`
                # schickt weder Rumpf noch Abfrageteil — der Pfad ist die einzige
                # Stelle, an der der Bereich mitgeht. `rstrip` fängt einen
                # Basispfad mit Schrägstrich am Ende ab, sonst entstünde ein
                # doppelter Trenner.
                "forget": f"{settings.substrate_forget_path.rstrip('/')}/{ns}",
            },
            client=client,
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(path, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SubstrateError(f"Substrat-Aufruf {path} fehlgeschlagen: {exc}") from exc
        data: Any = response.json()
        # Antworten normalisieren: immer ein Dict zurückgeben.
        return data if isinstance(data, dict) else {"result": data}

    async def _delete(self, path: str) -> dict[str, Any]:
        """Wie `_post`, aber löschend — eigener Weg, weil DELETE keinen Rumpf trägt.

        EIN 404 IST EINE EIGENE AUSNAHME, kein Erfolg: Er bedeutet, dass es unter
        dieser Kennung in diesem Bereich nichts (mehr) gibt. Für einen Aufrufer
        ist das etwas grundlegend anderes als eine Störung des Weges — im einen
        Fall ist das Ziel erreicht, im anderen steht der Versuch noch aus. Ohne
        die Unterscheidung ginge der Statuscode in `SubstrateError` verloren und
        beide Fälle sähen gleich aus.

        Umgedeutet wird trotzdem nichts: Auch der 404 WIRFT. Nur die ART wird
        unterscheidbar; was daraus folgt, entscheidet der Aufrufer.
        """
        try:
            response = await self._client.delete(path)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == httpx.codes.NOT_FOUND:
                raise SubstrateNotFoundError(
                    f"Substrat-Aufruf {path}: unter dieser Kennung liegt nichts."
                ) from exc
            raise SubstrateError(f"Substrat-Aufruf {path} fehlgeschlagen: {exc}") from exc
        except httpx.HTTPError as exc:
            # Netz-, Zeit- und Protokollfehler tragen keine Antwort — sie sind
            # immer eine Störung des Weges.
            raise SubstrateError(f"Substrat-Aufruf {path} fehlgeschlagen: {exc}") from exc
        data: Any = response.json()
        return data if isinstance(data, dict) else {"result": data}

    async def remember(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        """Legt eine Erinnerung im Substrat ab.

        `occurred_at` ist der Zeitpunkt, zu dem das Ereignis STATTFAND. Fehlt er,
        setzt die Gegenstelle den Zeitpunkt des Eingangs — und dann beschreibt
        jede zeitliche Auswertung dort den Spiegel-Lauf statt den Betrieb. Ein
        Nachtrag für Altbestand legt so den halben Bestand in dieselbe Stunde.

        Die Zeit als METADATUM mitzuschicken genügt dafür nicht: Die Gegenstelle
        wertet Metadaten nicht aus, sie liest dieses Feld. Deshalb geht die
        Ereigniszeit hier eigenständig mit, zusätzlich zur payload.
        """
        payload: dict[str, Any] = {"content": content, "namespace": self._namespace}
        if metadata:
            payload["metadata"] = metadata
        if occurred_at:
            payload["occurred_at"] = occurred_at
        return await self._post(self._paths["remember"], payload)

    async def forget(self, entry_id: str) -> dict[str, Any]:
        """Verlangt das Löschen einer Erinnerung.

        DER RÜCKWEG FÜR EIN LÖSCHVERLANGEN (Art. 17 DSGVO). Seit die
        Schichtnotiz gespiegelt wird (§12.4), verlässt beschreibender Text die
        Anlage — NER-maskiert, aber mit dokumentiertem Restrisiko. Ohne diesen
        Weg wäre ein Löschverlangen für den gespiegelten Teil nicht erfüllbar.

        Das Gedächtnis nimmt beim Löschen auch die aus dem Eintrag gewonnenen
        Aussagen mit, damit gelöschte Inhalte nicht über Umwege weiterwirken.
        Diese Zusicherung liegt dort, nicht hier — FOREMAN verlangt das Löschen
        und wertet die Antwort.

        Ein Fehlschlag WIRFT. Bei einem Löschverlangen ist die Erfolgsmeldung
        der ganze Nachweis; eine verschluckte Ausnahme wäre ein Häkchen ohne
        Wirkung.
        """
        kennung = entry_id.strip()
        if not kennung:
            # Ohne Kennung zeigte der Pfad auf die Sammlung statt auf einen
            # Eintrag — im günstigen Fall ein 405, im ungünstigen trifft es mehr
            # als gemeint. Der Fehler gehört vor den Aufruf.
            raise ValueError("Kennung der Erinnerung fehlt — Löschen ohne Ziel ist nicht zulässig")
        return await self._delete(f"{self._paths['forget']}/{kennung}")

    async def recall(self, query: str, *, max_results: int = 5) -> dict[str, Any]:
        """Sucht Erinnerungen im Substrat."""
        return await self._post(
            self._paths["recall"],
            {"query": query, "namespace": self._namespace, "max_results": max_results},
        )

    async def reason(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Stößt eine Reasoning-Operation des Substrats an."""
        return await self._post(
            self._paths["reason"],
            {"query": query, "namespace": self._namespace, **kwargs},
        )

    async def drift_status(self, **kwargs: Any) -> dict[str, Any]:
        """Fragt den Drift-/Stabilitäts-Status des Substrats ab."""
        return await self._post(
            self._paths["drift_status"], {"namespace": self._namespace, **kwargs}
        )

    async def reflect(self, **kwargs: Any) -> dict[str, Any]:
        """Fragt Profil/Statistiken (Reflexion) des Substrats ab."""
        return await self._post(self._paths["reflect"], {"namespace": self._namespace, **kwargs})

    async def aclose(self) -> None:
        """Schließt den HTTP-Client, falls dieser Client ihn besitzt."""
        if self._owns_client:
            await self._client.aclose()
