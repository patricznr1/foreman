// ============================================================
//  FOREMAN Frontend — app/login/page.tsx
//  Zweck: Anmeldung über den BFF (/api/session POST → httpOnly-Cookie). Nach
//         Erfolg Sprung auf das rollenspezifische Landing. Große Touch-Ziele,
//         Fehler als Live-Region, deutsche Hallensprache.
//  Architektur-Einordnung: Auth-Sicht (Schicht 3, client).
// ============================================================
"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import type { CurrentUser } from "@/lib/api/contracts";
import { landingRoute } from "@/lib/auth/roles";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/session", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        setError("Anmeldung fehlgeschlagen — bitte Zugangsdaten prüfen.");
        return;
      }
      const user = (await response.json()) as CurrentUser;
      router.push(landingRoute(user.role));
      router.refresh();
    } catch {
      setError("Verbindung fehlgeschlagen — bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface-canvas p-4">
      <form
        onSubmit={onSubmit}
        aria-label="Anmeldung"
        className="flex w-full max-w-sm flex-col gap-4 rounded-lg border border-line-subtle bg-surface-raised p-6"
      >
        <h1 className="text-h1 text-fg-primary">FOREMAN</h1>
        <p className="text-caption text-fg-muted">Anmeldung an der Produktionsplattform</p>
        {error ? (
          <p role="alert" className="text-body text-note-caveat">
            {error}
          </p>
        ) : null}
        <label className="flex flex-col gap-1 text-caption text-fg-secondary">
          E-Mail
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="touch-target rounded-md border border-line-strong bg-surface-overlay px-3 text-body text-fg-primary"
          />
        </label>
        <label className="flex flex-col gap-1 text-caption text-fg-secondary">
          Passwort
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="touch-target rounded-md border border-line-strong bg-surface-overlay px-3 text-body text-fg-primary"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="touch-target-safety rounded-md border border-line-strong bg-surface-overlay text-body text-fg-primary hover:bg-surface-overlay disabled:opacity-60"
        >
          {busy ? "Anmelden …" : "Anmelden"}
        </button>
      </form>
    </main>
  );
}
