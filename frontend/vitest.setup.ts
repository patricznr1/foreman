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

// jsdom hat kein ResizeObserver — die virtualisierte Alarmliste misst damit den
// Viewport (in Tests wird die Höhe ohnehin über den viewportHeight-Override gesetzt).
if (typeof globalThis !== "undefined" && !("ResizeObserver" in globalThis)) {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverStub;
}
