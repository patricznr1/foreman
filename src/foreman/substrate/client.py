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
        cls, settings: Settings, *, client: httpx.AsyncClient | None = None
    ) -> SubstrateClient:
        """Baut den Client aus der Config. Wirft, wenn keine Base-URL gesetzt ist."""
        if not settings.substrate_base_url:
            raise SubstrateNotConfiguredError(
                "SUBSTRATE_BASE_URL ist nicht gesetzt — Substrat-Anbindung fehlt."
            )
        return cls(
            base_url=settings.substrate_base_url,
            token=settings.substrate_token,
            timeout_s=settings.substrate_timeout_s,
            namespace=settings.substrate_namespace,
            paths={
                "remember": settings.substrate_remember_path,
                "recall": settings.substrate_recall_path,
                "reason": settings.substrate_reason_path,
                "drift_status": settings.substrate_drift_status_path,
                "reflect": settings.substrate_reflect_path,
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

    async def remember(
        self, content: str, *, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Legt eine Erinnerung im Substrat ab."""
        payload: dict[str, Any] = {"content": content, "namespace": self._namespace}
        if metadata:
            payload["metadata"] = metadata
        return await self._post(self._paths["remember"], payload)

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
