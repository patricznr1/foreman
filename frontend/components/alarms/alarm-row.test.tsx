// ============================================================
//  FOREMAN Frontend — components/alarms/alarm-row.test.tsx
//  Zweck: Zeile — Severity dreikanalig (Label sichtbar), 1-Hz-Puls NUR unquittiert-
//         kritisch, Drift-Klasse markiert, FCSM-Indikator, Querlinks, Quittier-Ziel.
// ============================================================
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NOW, alarm, machines, noNew, noShelf } from "@/lib/alarms/testing/fixtures";
import type { AlarmViewModel } from "@/lib/alarms/types";
import { buildAlarmViewModel } from "@/lib/alarms/view-model";
import { AlarmRow } from "./alarm-row";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(cleanup);

const ctx = (over = {}) => ({ machines, shelf: noShelf, now: NOW, newIds: noNew, ...over });
const vm = (over = {}): AlarmViewModel => buildAlarmViewModel(alarm(over), ctx());

const props = {
  canAcknowledge: true,
  online: true,
  onAcknowledged: vi.fn(),
  onShelve: vi.fn(),
  onUnshelve: vi.fn(),
};

describe("AlarmRow", () => {
  it("zeigt das Prioritäts-Label (dritter Kanal) + Maschine + Kurztext", () => {
    render(<AlarmRow vm={vm({ severity: "critical", message: "Lager heiß" })} {...props} />);
    expect(screen.getByText("Kritisch")).toBeInTheDocument();
    expect(screen.getByText("Presse 1")).toBeInTheDocument();
    expect(screen.getByText("Lager heiß")).toBeInTheDocument();
  });

  it("1-Hz-Puls NUR bei unquittiert-kritisch", () => {
    const { container } = render(<AlarmRow vm={vm({ severity: "critical" })} {...props} />);
    expect(container.querySelector(".attention-pulse")).not.toBeNull();
  });

  it("quittiert/nicht-kritisch → kein Puls", () => {
    const { container: ack } = render(
      <AlarmRow
        vm={vm({ severity: "critical", acknowledged_at: "2026-06-17T08:30:00Z" })}
        {...props}
      />,
    );
    expect(ack.querySelector(".attention-pulse")).toBeNull();
    cleanup();
    const { container: warn } = render(<AlarmRow vm={vm({ severity: "warning" })} {...props} />);
    expect(warn.querySelector(".attention-pulse")).toBeNull();
  });

  it("Drift → eigene markierte Klasse ('Abweichung') + FCSM 'außerhalb Spezifikation'", () => {
    render(<AlarmRow vm={vm({ code: "DRIFT", severity: "warning" })} {...props} />);
    expect(screen.getByText("Abweichung")).toBeInTheDocument();
    expect(screen.getByLabelText(/Außerhalb Spezifikation/)).toBeInTheDocument();
  });

  it("Querlinks → Maschine/Kette/Ausfall vorbereitet", () => {
    render(<AlarmRow vm={vm({ machine_id: 1, severity: "alarm" })} {...props} />);
    expect(screen.getByRole("link", { name: "Maschine" })).toHaveAttribute(
      "href",
      "/machines?machine=1",
    );
    expect(screen.getByRole("link", { name: "Kette" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ausfall?" })).toBeInTheDocument();
  });

  it("Quittier-Ziel vorhanden (zeilenspezifischer Accessible Name), wenn die Rolle quittieren darf", () => {
    render(<AlarmRow vm={vm({ machine_id: 1, code: "DRIFT", severity: "critical" })} {...props} />);
    // Accessible Name trägt den Maschinenbezug (mehrere Zeilen sonst nicht unterscheidbar).
    expect(
      screen.getByRole("button", { name: "Alarm an Presse 1 quittieren" }),
    ).toBeInTheDocument();
  });

  it("zurückgestellt: sichtbarer Zustand (Symbol+Text) + 'Einblenden' ruft onUnshelve (Touch-erreichbar)", async () => {
    const onUnshelve = vi.fn();
    const user = userEvent.setup();
    const shelvedVm = buildAlarmViewModel(alarm({ id: 50, machine_id: 1, severity: "critical" }), {
      machines,
      shelf: new Map([[50, NOW + 60_000]]),
      now: NOW,
      newIds: noNew,
    });
    render(<AlarmRow vm={shelvedVm} {...props} onUnshelve={onUnshelve} />);
    expect(screen.getAllByText(/Zurückgestellt/).length).toBeGreaterThan(0);
    // Im shelved-Zustand kein Quittier-Ziel, sondern die Rücknahme.
    expect(screen.queryByRole("button", { name: /quittieren/i })).toBeNull();
    await user.click(screen.getByRole("button", { name: /aufheben/i }));
    expect(onUnshelve).toHaveBeenCalledWith(50);
  });
});
