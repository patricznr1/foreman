// ============================================================
//  FOREMAN Frontend — lib/platform/use-audit.ts
//  Zweck: Anbindung des unveränderlich-lesenden Audit-Trails über den BFF (§22.1).
//         NUR-LESEND — keine Mutation, kein Schreibpfad. Re-Fetch, wenn sich die
//         (aus dem Filter abgeleitete) Query effektiv ändert; die Backend-
//         Reihenfolge (jüngste zuerst) bleibt erhalten. Dieser Hook wird AUSSCHLIESS-
//         LICH im Manager-Zweig gerendert — der Schichtleiter ruft GET /api/v1/audit
//         nie auf (gäbe 403, §22.1). Fünf Zustände über DataState.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useEffect, useRef, useState } from "react";
import type { DataState } from "@/lib/state/view-state";
import type { AuditFilter } from "./audit-filter";
import { assembleAuditRows } from "./audit-view-model";
import type { AuditRowModel, AuditEntryRead } from "./types";
import { auditEndpoint, fetchErrorKey } from "./url";

export interface UseAuditResult {
  state: DataState<AuditRowModel[]>;
}

/**
 * Lädt die gefilterte/paginierte Audit-Seite. Der Endpoint-String dient als
 * effektive Dependency — re-fetcht nur bei echter Query-Änderung (nicht bei
 * jedem Tastendruck, weil der Filter erst beim Anwenden in den State fließt).
 */
export function useAudit(filter: AuditFilter): UseAuditResult {
  const endpoint = auditEndpoint(filter);
  const [state, setState] = useState<DataState<AuditRowModel[]>>({ kind: "loading" });
  const inflight = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    setState({ kind: "loading" });
    void (async () => {
      try {
        const res = await fetch(endpoint, {
          credentials: "same-origin",
          cache: "no-store",
          signal: controller.signal,
        });
        if (!res.ok) {
          setState({ kind: "error", message: fetchErrorKey(res.status) });
          return;
        }
        const raw = (await res.json()) as AuditEntryRead[];
        const rows = assembleAuditRows(raw);
        setState(rows.length === 0 ? { kind: "empty" } : { kind: "cached", data: rows });
      } catch (caught) {
        if ((caught as Error).name === "AbortError") {
          return;
        }
        setState({ kind: "error", message: "load-failed" });
      }
    })();
    return () => controller.abort();
  }, [endpoint]);

  return { state };
}
