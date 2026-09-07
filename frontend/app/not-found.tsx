// ============================================================
//  FOREMAN Frontend — app/not-found.tsx
//  Zweck: Die Nicht-gefunden-Seite in Hallensprache. Ohne diese Datei liefert
//         Next.js seine englische Standardseite — mitten in einer durchgehend
//         deutschen Anwendung. Ein Tippfehler in der Adresse führt jetzt zurück
//         zur Anmeldung statt auf eine fremdsprachige Fremdseite.
//  Architektur-Einordnung: Routen-Einstieg (Schicht 2, server).
// ============================================================
import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-surface-canvas p-4">
      <section
        aria-label="Seite nicht gefunden"
        className="flex w-full max-w-sm flex-col gap-4 rounded-lg border border-line-subtle bg-surface-raised p-6"
      >
        <h1 className="text-h1 text-fg-primary">Seite nicht gefunden</h1>
        <p className="text-body text-fg-secondary">
          Unter dieser Adresse gibt es nichts. Der Einstieg in die Produktionsplattform ist die
          Anmeldung.
        </p>
        <Link
          href="/login"
          className="touch-target inline-flex items-center justify-center rounded-md border border-line-strong bg-surface-overlay px-3 text-body text-fg-primary hover:bg-surface-overlay focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          Zur Anmeldung
        </Link>
      </section>
    </main>
  );
}
