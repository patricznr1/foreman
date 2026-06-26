// ============================================================
//  FOREMAN Frontend — components/shell/primary-nav.tsx
//  Zweck: Rollengefilterte Primärnavigation (§3.1/§3.3) — höchstens 7 begehbare
//         Einträge, keiner ohne zugehörige Aktion. Spiegelt die Server-
//         Autorisierung. Ein als `disabled` markierter Eintrag (z. B. eine
//         angekündigte, noch nicht freigeschaltete Funktion) erscheint sichtbar,
//         aber ausgegraut und NICHT klickbar (kein Link, kein Routing-Ziel).
//         Vertikal am Leitstand/Tablet, horizontal als Mobil-Leiste.
//  Architektur-Einordnung: Persistentes Rahmenelement (Schicht 2, client).
// ============================================================
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { visibleNav } from "@/lib/auth/roles";
import { useSession } from "@/lib/auth/use-session";
import { cx } from "@/lib/ui/cx";

export function PrimaryNav({
  orientation = "vertical",
  ariaLabel = "Hauptnavigation",
}: {
  orientation?: "vertical" | "horizontal";
  ariaLabel?: string;
}) {
  const user = useSession();
  const pathname = usePathname();
  const items = visibleNav(user.role);

  return (
    <nav
      aria-label={ariaLabel}
      className={cx("flex gap-1", orientation === "vertical" ? "flex-col" : "flex-row flex-wrap")}
    >
      {items.map((item) => {
        // Sichtbar, aber deaktiviert: kein Link, kein Routing-Ziel, kein Klick-Handler.
        if (item.disabled || item.href === null) {
          return (
            <span
              key={item.id}
              aria-disabled="true"
              title="In Vorbereitung"
              className="flex cursor-default items-center rounded-md px-3 text-body text-fg-muted opacity-70 touch-target"
            >
              {item.label}
            </span>
          );
        }
        const href = item.href;
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={item.id}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cx(
              "flex items-center rounded-md px-3 text-body touch-target",
              active
                ? "bg-surface-overlay text-fg-primary"
                : "text-fg-secondary hover:bg-surface-raised",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
