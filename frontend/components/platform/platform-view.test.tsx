// ============================================================
//  FOREMAN Frontend — components/platform/platform-view.test.tsx
//  Zweck: Sichert den Rollen-Split der Sektion I (Studie-Matrix §4I): Manager sieht
//         Topologie UND Audit-Trail (beide Tabs, beide Daten geladen); Schichtleiter
//         sieht NUR die Topologie, KEIN Audit-Tab — und der FE ruft GET /api/v1/audit
//         für ihn NIE auf (Kern-Security: Sichtbarkeit ≤ Server-Guard). Werker/
//         Techniker erreichen keinen Inhalt. Plus Edge: leere Topologie, Refresh.
// ============================================================
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CurrentUser, Role } from "@/lib/api/contracts";
import { makeAuditEntry, makeTopologyView } from "@/lib/platform/testing/fixtures";
import type { TopologyViewRead } from "@/lib/platform/types";
import { PlatformView } from "./platform-view";

function user(role: Role): CurrentUser {
  return { id: 1, email: "u@example.com", role, assigned_line_ids: [], assigned_machine_ids: [] };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as unknown as Response;
}

function installFetch(topology: TopologyViewRead = makeTopologyView()) {
  const mock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/v1/topology")) {
      return Promise.resolve(jsonResponse(topology));
    }
    if (url.includes("/api/v1/audit")) {
      return Promise.resolve(jsonResponse([makeAuditEntry()]));
    }
    return Promise.resolve(jsonResponse({ detail: "not found" }, 404));
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

function auditCalls(mock: ReturnType<typeof installFetch>): number {
  return mock.mock.calls.filter(([input]) => String(input).includes("/api/v1/audit")).length;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PlatformView — Rollen-Split", () => {
  it("Manager: sieht beide Tabs und lädt Topologie UND Audit", async () => {
    const mock = installFetch();
    render(<PlatformView user={user("manager")} />);
    await screen.findByTestId("topology-graph");
    expect(screen.getByRole("tab", { name: "Topologie" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Audit-Trail" })).toBeInTheDocument();
    // Beide Panels sind gemountet → der Audit wird (für den Manager erlaubt) geladen.
    await waitFor(() => expect(auditCalls(mock)).toBeGreaterThan(0));
  });

  it("Manager: Tabs sind per Pfeiltasten navigierbar (roving tabindex + Wraparound)", async () => {
    installFetch();
    render(<PlatformView user={user("manager")} />);
    await screen.findByTestId("topology-graph");
    const topoTab = screen.getByRole("tab", { name: "Topologie" });
    const auditTab = screen.getByRole("tab", { name: "Audit-Trail" });

    expect(topoTab).toHaveAttribute("aria-selected", "true");
    expect(topoTab).toHaveAttribute("tabindex", "0");
    expect(auditTab).toHaveAttribute("tabindex", "-1");

    topoTab.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(auditTab).toHaveAttribute("aria-selected", "true");

    await userEvent.keyboard("{ArrowRight}"); // Wraparound → erste Tab
    expect(topoTab).toHaveAttribute("aria-selected", "true");

    await userEvent.keyboard("{ArrowLeft}"); // Wraparound rückwärts → letzte Tab
    expect(auditTab).toHaveAttribute("aria-selected", "true");
  });

  it("Schichtleiter: nur Topologie, KEIN Audit-Tab — und /api/v1/audit wird NIE aufgerufen", async () => {
    const mock = installFetch();
    render(<PlatformView user={user("shift_lead")} />);
    await screen.findByTestId("topology-graph");
    expect(screen.queryByRole("tab", { name: "Audit-Trail" })).toBeNull();
    expect(screen.queryByRole("tablist")).toBeNull();
    // Kern-Security: für den Schichtleiter darf der FE den Audit-Endpoint nicht treffen.
    expect(auditCalls(mock)).toBe(0);
  });

  it("Werker und Techniker: kein Inhalt, kein Daten-Abruf", () => {
    for (const role of ["worker", "technician"] as const) {
      const mock = installFetch();
      const { unmount } = render(<PlatformView user={user(role)} />);
      expect(screen.getByText(/Manager und Schichtleiter vorbehalten/)).toBeInTheDocument();
      expect(mock).not.toHaveBeenCalled();
      unmount();
      vi.unstubAllGlobals();
    }
  });
});

describe("PlatformView — Edge/Race", () => {
  it("leere Topologie → ruhiger Leer-Zustand statt Fehlbild", async () => {
    installFetch(makeTopologyView({ nodes: [], vision: [] }));
    render(<PlatformView user={user("shift_lead")} />);
    expect(await screen.findByText(/keine Daten/)).toBeInTheDocument();
  });

  it("Refresh löst einen erneuten Topologie-Abruf aus (bewusste Aktion)", async () => {
    const mock = installFetch();
    render(<PlatformView user={user("shift_lead")} />);
    await screen.findByTestId("topology-graph");
    const before = mock.mock.calls.filter(([u]) => String(u).includes("/api/v1/topology")).length;
    await userEvent.click(screen.getByRole("button", { name: "Aktualisieren" }));
    await waitFor(() =>
      expect(
        mock.mock.calls.filter(([u]) => String(u).includes("/api/v1/topology")).length,
      ).toBeGreaterThan(before),
    );
  });

  it("Topologie: transienter Refresh-Fehler hält den letzten Snapshot (Degradation)", async () => {
    let topoCalls = 0;
    const mock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/topology")) {
        topoCalls += 1;
        return Promise.resolve(
          topoCalls === 1 ? jsonResponse(makeTopologyView()) : jsonResponse({ detail: "boom" }, 500),
        );
      }
      return Promise.resolve(jsonResponse([makeAuditEntry()]));
    });
    vi.stubGlobal("fetch", mock);
    render(<PlatformView user={user("shift_lead")} />);
    await screen.findByTestId("topology-graph");
    await userEvent.click(screen.getByRole("button", { name: "Aktualisieren" }));
    await waitFor(() => expect(topoCalls).toBeGreaterThan(1));
    // Trotz fehlgeschlagenem Refresh bleibt der letzte Snapshot sichtbar (kein Fehlbild).
    expect(screen.getByTestId("topology-graph")).toBeInTheDocument();
  });

  it("Topologie: fataler Fehler (403) zeigt den Fehlerzustand statt eines leeren Bilds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/v1/topology")) {
          return Promise.resolve(jsonResponse({ detail: "forbidden" }, 403));
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );
    render(<PlatformView user={user("shift_lead")} />);
    expect(await screen.findByText(/Kein Zugriff auf diese Sicht/)).toBeInTheDocument();
  });

  it("die Substrat-Probe lässt sich abschalten (probe=false im Query)", async () => {
    const mock = installFetch();
    render(<PlatformView user={user("shift_lead")} />);
    await screen.findByTestId("topology-graph");
    await userEvent.click(screen.getByRole("checkbox", { name: /Substrat live prüfen/ }));
    await waitFor(() =>
      expect(mock.mock.calls.some(([u]) => String(u).includes("probe=false"))).toBe(true),
    );
  });
});
