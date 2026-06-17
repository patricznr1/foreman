// ============================================================
//  FOREMAN Frontend — components/shell/command-palette.test.tsx
//  Zweck: Cmd-K → H. Die Befehlsleiste bietet bei Eingabe eine direkte
//         Bedeutungssuche und springt mit der Anfrage nach /memory?q=… —
//         das Gedächtnis ist von überall erreichbar (Studie §3.3/§4H).
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
  it("bietet bei Eingabe eine Suche im Gedächtnis und springt nach /memory?q=", async () => {
    render(
      <SessionProvider user={USER}>
        <CommandPalette />
      </SessionProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: /Suchen/ }));
    await userEvent.type(screen.getByLabelText("Befehl oder Suche"), "Lager heiß");
    await userEvent.click(screen.getByRole("button", { name: /Im Gedächtnis suchen/ }));
    expect(push).toHaveBeenCalledWith("/memory?q=Lager%20hei%C3%9F");
  });
});
