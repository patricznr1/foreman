// ============================================================
//  FOREMAN Frontend — components/shell/command-palette.tsx
//  Zweck: Befehlsleiste (Cmd-K, §3.3) — Sprung zu Sektionen und zum Gedächtnis
//         (H) von überall. Vollständig tastaturbedienbar (Cmd/Ctrl+K öffnet,
//         Pfeiltasten, Enter, Esc), Fokus wandert ins Eingabefeld, role=dialog.
//  Architektur-Einordnung: Persistentes Rahmenelement (Schicht 2, client).
// ============================================================
"use client";

import { useRouter } from "next/navigation";
import { type KeyboardEvent as ReactKeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { type NavItem, visibleNav } from "@/lib/auth/roles";
import { useSession } from "@/lib/auth/use-session";
import { cx } from "@/lib/ui/cx";

export function CommandPalette() {
  const user = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = useMemo<NavItem[]>(() => visibleNav(user.role), [user.role]);
  const filtered = useMemo(
    () => commands.filter((c) => c.label.toLowerCase().includes(query.trim().toLowerCase())),
    [commands, query],
  );

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

  const go = useCallback(
    (item: NavItem | undefined): void => {
      if (item === undefined) {
        return;
      }
      setOpen(false);
      router.push(item.href);
    },
    [router],
  );

  function onInputKey(event: ReactKeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      go(filtered[activeIndex]);
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
              placeholder="Sektion springen oder Gedächtnis durchsuchen …"
              aria-label="Befehl oder Suche"
              className="w-full bg-transparent px-4 py-3 text-body text-fg-primary outline-none"
            />
            <ul
              aria-label="Sprungziele"
              className="max-h-72 overflow-auto border-t border-line-subtle"
            >
              {filtered.length === 0 ? (
                <li className="px-4 py-3 text-caption text-fg-muted">Kein Treffer</li>
              ) : (
                filtered.map((item, index) => (
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
