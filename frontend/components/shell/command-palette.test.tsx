// ============================================================
//  FOREMAN Frontend — components/shell/command-palette.test.tsx
//  Zweck: Cmd-K → H. Die Befehlsleiste bietet bei Eingabe eine direkte
//         Archiv-Suche und springt mit der Anfrage nach /archive?q=… (Studie
//         §3.3/§4H). Ein deaktivierter Nav-Eintrag erzeugt KEINEN ausführbaren Befehl.
// ============================================================
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { CurrentUser } from "@/lib/api/contracts";
import { SessionProvider } from "@/lib/auth/use-session";
import { CommandPalette } from "./command-palette";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const USER: CurrentUser = {
  id: 1,
  email: "w@example.com",
  role: "worker",
  assigned_line_ids: [],
  assigned_machine_ids: [],
};

describe("CommandPalette — H von überall", () => {
  it("bietet bei Eingabe eine Suche im Archiv und springt nach /archive?q=", async () => {
    render(
      <SessionProvider user={USER}>
        <CommandPalette />
      </SessionProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: /Suchen/ }));
    await userEvent.type(screen.getByLabelText("Befehl oder Suche"), "Lager heiß");
    await userEvent.click(screen.getByRole("button", { name: /Im Archiv suchen/ }));
    expect(push).toHaveBeenCalledWith("/archive?q=Lager%20hei%C3%9F");
  });

  it("der deaktivierte Eintrag 'Hatten wir das schon mal' erzeugt keinen Sprung-Befehl", async () => {
    render(
      <SessionProvider user={USER}>
        <CommandPalette />
      </SessionProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: /Suchen/ }));
    await userEvent.type(screen.getByLabelText("Befehl oder Suche"), "Hatten wir das schon mal");
    // Die Such-Aktion ("Im Archiv suchen: …") ist da — aber KEIN ausführbarer Sprung
    // zum deaktivierten Eintrag (kein Routing-Ziel).
    expect(screen.getByRole("button", { name: /Im Archiv suchen/ })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Hatten wir das schon mal" }),
    ).not.toBeInTheDocument();
  });
});
