// ============================================================
//  FOREMAN Frontend — components/capture/sync-status.test.tsx
//  Zweck: Sichert die Sync-Status-Anzeige (Live-Region, ruhiges Wording).
// ============================================================
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SyncStatus } from "./sync-status";

describe("SyncStatus", () => {
  it("ist im Ruhezustand unsichtbar (kein Lärm)", () => {
    const { container } = render(<SyncStatus state={{ kind: "idle" }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("meldet erfolgreiche Synchronisation über eine höfliche Live-Region", () => {
    render(<SyncStatus state={{ kind: "synced", at: "2026-06-17T15:00:00+00:00" }} />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent("synchronisiert");
  });

  it("benennt den Offline-Puffer NEUTRAL (kein Alarm-Wording)", () => {
    render(<SyncStatus state={{ kind: "queued", pending: 2 }} />);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/werden gesendet, sobald online/);
    const text = status.textContent?.toLowerCase() ?? "";
    expect(text).not.toContain("fehler");
    expect(text).not.toContain("alarm");
  });

  it("zeigt während des Sendens einen Hinweis", () => {
    render(<SyncStatus state={{ kind: "sending" }} />);
    expect(screen.getByRole("status")).toHaveTextContent(/wird gesendet/);
  });
});
