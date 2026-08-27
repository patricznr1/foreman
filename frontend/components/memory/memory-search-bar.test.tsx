// ============================================================
//  FOREMAN Frontend — components/memory/memory-search-bar.test.tsx
//  Zweck: Stichwort-Suchzeile des Archivs — Eingabe löst mit allen Quellen aus;
//         offline deaktiviert mit Grund; Maschinen-Filter + Quellen-Toggles nur für
//         Rollen mit Filter; Deaktivieren einer Quelle entfernt sie aus sources[].
// ============================================================
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { VERFUEGBARE_QUELLEN } from "@/lib/memory/source";
import { MemorySearchBar } from "./memory-search-bar";

/**
 * Beschriftungen der Umschalter, aus DERSELBEN Liste abgeleitet, die die Zeile
 * benutzt.
 *
 * WARUM NICHT FEST VERDRAHTET: Eine feste Liste im Test bemerkt eine NEUE Quelle
 * nicht — sie prueft die drei, die sie kennt, bleibt gruen, und die vierte
 * erscheint ungeprueft in der Halle. Genau das ist am 27.08.2026 beinahe
 * passiert: Der Test iterierte ueber drei Namen ohne Gesamtzahl, und das
 * Hinzufuegen der vierten Quelle haette ihn nicht angefasst.
 */
const BESCHRIFTUNG: Record<string, string> = {
  note: "Schichtnotizen",
  maintenance: "Wartung",
  alarm: "Alarme",
  memory: "Gedächtnis",
};
const ALLE_QUELLEN = [...VERFUEGBARE_QUELLEN];
const ALLE_NAMEN = ALLE_QUELLEN.map((q) => BESCHRIFTUNG[q]);

describe("MemorySearchBar (Archiv)", () => {
  it("nimmt ein Stichwort und löst beim Absenden mit allen Quellen aus", async () => {
    const onSubmit = vi.fn();
    render(<MemorySearchBar onSubmit={onSubmit} busy={false} canFilter={false} machines={[]} />);
    await userEvent.type(screen.getByLabelText(/Stichwort/), "Fett");
    await userEvent.click(screen.getByRole("button", { name: "Suchen" }));
    expect(onSubmit).toHaveBeenCalledWith("Fett", null, ALLE_QUELLEN);
  });

  it("deaktiviert das Absenden offline mit sichtbarem Grund", () => {
    render(
      <MemorySearchBar
        onSubmit={vi.fn()}
        busy={false}
        canFilter={false}
        machines={[]}
        disabledReason="Offline — neue Suche nicht möglich"
      />,
    );
    expect(screen.getByRole("button", { name: "Suchen" })).toBeDisabled();
    expect(screen.getByText(/Offline/)).toBeInTheDocument();
  });

  it("zeigt Maschinen-Filter und Quellen-Toggles nur für Rollen mit Filter", () => {
    const { rerender } = render(
      <MemorySearchBar onSubmit={vi.fn()} busy={false} canFilter={false} machines={[7]} />,
    );
    expect(screen.queryByLabelText("Maschine")).toBeNull();
    expect(screen.queryByRole("group", { name: "Quellen" })).toBeNull();
    rerender(<MemorySearchBar onSubmit={vi.fn()} busy={false} canFilter machines={[7]} />);
    expect(screen.getByLabelText("Maschine")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Quellen" })).toBeInTheDocument();
  });

  it("Default: alle verfügbaren Quellen-Toggles sind aktiv (aria-pressed)", () => {
    render(<MemorySearchBar onSubmit={vi.fn()} busy={false} canFilter machines={[]} />);
    for (const name of ALLE_NAMEN) {
      expect(screen.getByRole("button", { name })).toHaveAttribute("aria-pressed", "true");
    }
  });

  it("das Gedächtnis IST eine angebotene Quelle (Schalter-Entscheidung, festgenagelt)", () => {
    // Diese Zusicherung leitet BEWUSST NICHT aus VERFUEGBARE_QUELLEN ab — sonst
    // prüfte sie sich selbst. Sie nagelt eine Entscheidung fest: Seit dem
    // 27.08.2026 ist die vierte Quelle freigegeben (GROUND_TRUTH §15.10, sieben
    // Freigabe-Bedingungen, Register C-066/C-068). Wer sie wieder abschaltet,
    // ändert diesen Test WISSENTLICH mit — und legt dabei auch
    // FOREMAN_ARCHIVE_SUBSTRATE_ENABLED um, sonst fragt die Anzeige eine Quelle
    // an, die nie befragt wird.
    render(<MemorySearchBar onSubmit={vi.fn()} busy={false} canFilter machines={[]} />);
    expect(screen.getByRole("button", { name: "Gedächtnis" })).toBeInTheDocument();
  });

  it("die Zeile zeigt GENAU die verfügbaren Quellen — keine mehr, keine weniger", () => {
    // Die Zusicherung aus `source.ts`: VERFUEGBARE_QUELLEN ist die EINZIGE
    // Stelle, die entscheidet, was angeboten und angefragt wird. Ohne diesen
    // Test ist das eine Behauptung im Kommentar. Eine zusätzliche Schaltfläche
    // fiele sonst niemandem auf — und sie fragt eine Quelle an, die das Backend
    // womöglich gar nicht befragt.
    render(<MemorySearchBar onSubmit={vi.fn()} busy={false} canFilter machines={[]} />);
    const gruppe = screen.getByRole("group", { name: "Quellen" });
    const beschriftungen = Array.from(gruppe.querySelectorAll("button")).map((b) =>
      b.textContent?.trim(),
    );
    expect(beschriftungen).toEqual(ALLE_NAMEN);
  });

  it("Deaktivieren einer Quelle entfernt sie aus dem sources[]-Argument des Requests", async () => {
    const onSubmit = vi.fn();
    render(<MemorySearchBar onSubmit={onSubmit} busy={false} canFilter machines={[]} />);
    await userEvent.type(screen.getByLabelText(/Stichwort/), "Fett");
    await userEvent.click(screen.getByRole("button", { name: "Wartung" }));
    await userEvent.click(screen.getByRole("button", { name: "Suchen" }));
    expect(onSubmit).toHaveBeenCalledWith(
      "Fett",
      null,
      ALLE_QUELLEN.filter((q) => q !== "maintenance"),
    );
  });

  it("alle Quellen deaktiviert → Absenden gesperrt mit Hinweis", async () => {
    const onSubmit = vi.fn();
    render(<MemorySearchBar onSubmit={onSubmit} busy={false} canFilter machines={[]} />);
    for (const name of ALLE_NAMEN) {
      await userEvent.click(screen.getByRole("button", { name }));
    }
    expect(screen.getByRole("button", { name: "Suchen" })).toBeDisabled();
    expect(screen.getByText(/Mindestens eine Quelle/)).toBeInTheDocument();
  });

  it("ein Deep-Link-Wechsel setzt Maschinen-Filter und Quellen-Toggles zurück", async () => {
    const onSubmit = vi.fn();
    const { rerender } = render(
      <MemorySearchBar onSubmit={onSubmit} busy={false} canFilter machines={[7]} defaultQuery="alt" />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Wartung" })); // eine Quelle deaktivieren
    rerender(
      <MemorySearchBar onSubmit={onSubmit} busy={false} canFilter machines={[7]} defaultQuery="neu" />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Suchen" }));
    expect(onSubmit).toHaveBeenCalledWith("neu", null, ALLE_QUELLEN);
  });
});
