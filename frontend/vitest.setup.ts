// ============================================================
//  FOREMAN Frontend — vitest.setup.ts
//  Zweck: Test-Setup — jest-dom-Matcher für vitest, DOM-Cleanup nach jedem Test,
//         matchMedia-Polyfill (jsdom kennt es nicht; Theme/Reduced-Motion brauchen es).
// ============================================================
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

// jsdom hat kein matchMedia — Theme-/prefers-reduced-motion-Logik braucht es.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
}
