// ============================================================
//  FOREMAN Frontend — components/shell/command-palette.tsx
//  Zweck: Befehlsleiste (Cmd-K, §3.3) — Sprung zu Sektionen UND direkte
//         Archiv-Suche (H) von überall: was getippt wird, lässt sich als Suche an
//         /archive übergeben (Cmd-K → H, Studie §3.3/§4H). Deaktivierte Nav-Einträge
//         (kein Routing-Ziel) erscheinen NICHT als ausführbarer Befehl.
//         Vollständig tastaturbedienbar (Cmd/Ctrl+K öffnet, Pfeiltasten, Enter,
//         Esc), Fokus wandert ins Eingabefeld, role=dialog.
//  Architektur-Einordnung: Persistentes Rahmenelement (Schicht 2, client).
// ============================================================
"use client";

import { useRouter } from "next/navigation";
import { type KeyboardEvent as ReactKeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { canAccessSection, visibleNav } from "@/lib/auth/roles";
import { useSession } from "@/lib/auth/use-session";
import { cx } from "@/lib/ui/cx";

interface Command {
  id: string;
  /** Sichtbares Label (Hallensprache). */
  label: string;
  /** Aktion beim Auswählen (Sprung oder Suche). */
  run: () => void;
}

export function CommandPalette() {
  const user = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const nav = useMemo(() => visibleNav(user.role), [user.role]);
  const trimmed = query.trim();
  const lower = trimmed.toLowerCase();

  const items = useMemo<Command[]>(() => {
    const list: Command[] = [];
    // Direkte Archiv-Suche — nur wenn die Rolle das Archiv sehen darf
    // (Sichtbarkeit <= Backend-Autorisierung). Springt mit der Anfrage nach H.
    if (trimmed.length > 0 && canAccessSection(user.role, "H")) {
      const href = `/archive?q=${encodeURIComponent(trimmed)}`;
      list.push({
        id: "__search",
        label: `Im Archiv suchen: ${trimmed}`,
        run: () => {
          setOpen(false);
          router.push(href);
        },
      });
    }
    for (const item of nav) {
      // Deaktivierte Einträge (kein Routing-Ziel) erzeugen KEINEN ausführbaren Befehl.
      if (item.disabled || item.href === null) {
        continue;
      }
      const href = item.href;
      if (item.label.toLowerCase().includes(lower)) {
        list.push({
          id: item.id,
          label: item.label,
          run: () => {
            setOpen(false);
            router.push(href);
          },
        });
      }
    }
    return list;
  }, [trimmed, lower, nav, user.role, router]);

  useEffect(() => {
    function onKey(event: globalThis.KeyboardEvent): void {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setActiveIndex(0);
      inputRef.current?.focus();
    } else {
      setQuery("");
    }
  }, [open]);

  const go = useCallback((item: Command | undefined): void => {
    if (item === undefined) {
      return;
    }
    item.run();
  }, []);

  function onInputKey(event: ReactKeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (items.length === 0 ? 0 : Math.min(index + 1, items.length - 1)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      go(items[activeIndex]);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-keyshortcuts="Meta+K Control+K"
        aria-haspopup="dialog"
        className="touch-target flex items-center gap-2 rounded-md border border-line-subtle px-3 text-caption text-fg-secondary hover:bg-surface-overlay"
      >
        <span>Suchen / Sprung</span>
        <kbd className="rounded bg-surface-overlay px-1 text-fg-muted">⌘K</kbd>
      </button>

      {open ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]">
          <button
            type="button"
            aria-label="Befehlsleiste schließen"
            tabIndex={-1}
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-surface-canvas/70"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Befehlsleiste"
            className="relative z-10 w-full max-w-lg overflow-hidden rounded-lg border border-line-strong bg-surface-overlay shadow-xl"
          >
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActiveIndex(0);
              }}
              onKeyDown={onInputKey}
              placeholder="Sektion springen oder Archiv durchsuchen …"
              aria-label="Befehl oder Suche"
              className="w-full bg-transparent px-4 py-3 text-body text-fg-primary outline-none"
            />
            <ul aria-label="Sprungziele und Suche" className="max-h-72 overflow-auto border-t border-line-subtle">
              {items.length === 0 ? (
                <li className="px-4 py-3 text-caption text-fg-muted">Kein Treffer</li>
              ) : (
                items.map((item, index) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => go(item)}
                      onMouseEnter={() => setActiveIndex(index)}
                      className={cx(
                        "touch-target flex w-full items-center px-4 text-left text-body",
                        index === activeIndex
                          ? "bg-surface-raised text-fg-primary"
                          : "text-fg-secondary",
                      )}
                    >
                      {item.label}
                    </button>
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>
      ) : null}
    </>
  );
}
