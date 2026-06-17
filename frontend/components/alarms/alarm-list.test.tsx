// ============================================================
//  FOREMAN Frontend — components/alarms/alarm-list.test.tsx
//  Zweck: Virtualisierung (nur Sichtbares im DOM), Flood-Bündel-Toggle, Live-Regionen
//         je Dringlichkeit, kein Listen-Sprung (deterministisch über die Overrides).
// ============================================================
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { assembleAlarmView, defaultFilter } from "@/lib/alarms/assemble";
import { alarm, machines, NOW, noNew, noShelf } from "@/lib/alarms/testing/fixtures";
import { AlarmList } from "./alarm-list";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(cleanup);

const baseOptions = {
  machines,
  shelf: noShelf,
  now: NOW,
  newIds: noNew,
  filter: defaultFilter(),
  groupMode: "priority" as const,
  expandedBundles: new Set<string>(),
};

const listProps = {
  canAcknowledge: true,
  online: true,
  onAcknowledged: vi.fn(),
  onShelve: vi.fn(),
  onUnshelve: vi.fn(),
  expandedBundles: new Set<string>(),
  onToggleBundle: vi.fn(),
};

describe("AlarmList — Virtualisierung", () => {
  it("rendert bei großer Liste nur das sichtbare Fenster (nicht alle Zeilen)", () => {
    const alarms = Array.from({ length: 60 }, (_n, i) =>
      alarm({ id: i + 1, machine_id: (i % 3) + 1, severity: "alarm", code: `C${i}` }),
    );
    const view = assembleAlarmView(alarms, baseOptions);
    render(
      <AlarmList rows={view.rows} {...listProps} viewportHeight={160} scrollTop={0} rowHeight={80} />,
    );
    // Viewport 160 / 80 = 2 sichtbar + Overscan → deutlich weniger als 60 Artikel.
    expect(screen.getAllByRole("article").length).toBeLessThan(20);
  });

  it("zeigt den prioritätsgestaffelten Gruppenkopf", () => {
    const view = assembleAlarmView([alarm({ severity: "critical" })], baseOptions);
    render(<AlarmList rows={view.rows} {...listProps} viewportHeight={600} scrollTop={0} />);
    expect(screen.getByRole("heading", { name: /Kritisch/ })).toBeInTheDocument();
  });
});

describe("AlarmList — Flood-Bündel & A11y", () => {
  it("Flood → eine Bündel-Zeile; Aufklappen meldet den Schlüssel", async () => {
    const flood = Array.from({ length: 12 }, (_n, i) =>
      alarm({ id: i + 1, machine_id: 1, code: "OVERLOAD", severity: "alarm" }),
    );
    const view = assembleAlarmView(flood, baseOptions);
    const onToggle = vi.fn();
    const user = userEvent.setup();
    render(
      <AlarmList
        {...listProps}
        rows={view.rows}
        onToggleBundle={onToggle}
        viewportHeight={600}
        scrollTop={0}
      />,
    );
    expect(screen.getByText("12 Alarme")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Aufklappen" }));
    expect(onToggle).toHaveBeenCalledWith("3|OVERLOAD");
  });

  it("Flood-Bündel mit unquittiert-kritischen Mitgliedern trägt den 1-Hz-Puls (ISA-18.2)", () => {
    const flood = Array.from({ length: 12 }, (_n, i) =>
      alarm({ id: i + 1, machine_id: 1, code: "OVERLOAD", severity: "critical" }),
    );
    const view = assembleAlarmView(flood, baseOptions);
    const { container } = render(
      <AlarmList {...listProps} rows={view.rows} viewportHeight={600} scrollTop={0} />,
    );
    expect(screen.getByText("12 Alarme")).toBeInTheDocument();
    // Der Unquittiert-Puls überlebt die Bündelung — sonst verschwindet er im dichtesten Fall.
    expect(container.querySelector(".attention-pulse")).not.toBeNull();
  });

  it("Live-Regionen je Dringlichkeit (assertiv/höflich) tragen die Ansage", () => {
    const view = assembleAlarmView([alarm({ severity: "alarm" })], baseOptions);
    render(
      <AlarmList
        {...listProps}
        rows={view.rows}
        assertiveMessage="1 neue dringende Alarme"
        politeMessage="2 neue Alarme"
        viewportHeight={600}
        scrollTop={0}
      />,
    );
    expect(screen.getByText("1 neue dringende Alarme")).toBeInTheDocument();
    expect(screen.getByText("2 neue Alarme")).toBeInTheDocument();
  });
});
