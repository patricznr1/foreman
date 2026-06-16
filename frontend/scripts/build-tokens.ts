// ============================================================
//  FOREMAN Frontend — scripts/build-tokens.ts
//  Zweck: Generiert app/styles/tokens.generated.css aus der EINZIGEN Token-Quelle
//         (tokens/primitive.ts + tokens/themes.ts, Studie §5.7). Speist Tailwind-
//         Theme (@theme → Utilities) UND Runtime-CSS-Variablen (Theme-Wechsel
//         ändert eine Ebene, nicht hunderte Komponenten).
//  Aufruf: `npm run tokens:build` (schreibt) · `npm run tokens:check` (CI: prüft,
//         dass die committete CSS zur Quelle passt — sonst Exit 1).
//  Architektur-Einordnung: Build-Werkzeug des Design-Systems (Schicht 0).
// ============================================================
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { fontSize, motion, radius, touch } from "../tokens/primitive";
import { SEMANTIC_COLOR_TOKENS, themes } from "../tokens/themes";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT_PATH = join(HERE, "..", "app", "styles", "tokens.generated.css");

/** camelCase → kebab-case (bodyL → body-l). */
function kebab(value: string): string {
  return value.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
}

function buildCss(): string {
  const colorUtilities = SEMANTIC_COLOR_TOKENS.map(
    (token) => `  --color-${token}: var(--tk-${token});`,
  ).join("\n");

  const fontSizeVars = Object.entries(fontSize)
    .map(([key, value]) => `  --text-${kebab(key)}: ${value};`)
    .join("\n");

  const darkVars = SEMANTIC_COLOR_TOKENS.map(
    (token) => `  --tk-${token}: ${themes.dark[token]};`,
  ).join("\n");

  const lightVars = SEMANTIC_COLOR_TOKENS.map(
    (token) => `  --tk-${token}: ${themes["hc-light"][token]};`,
  ).join("\n");

  // Theme-agnostische Maße (Touch/Motion) — eine Quelle, im :root verfügbar.
  const scaleVars = [
    `  --touch-min: ${touch.min};`,
    `  --touch-safety: ${touch.safety};`,
    `  --touch-action: ${touch.action};`,
    `  --touch-gap: ${touch.gap};`,
    `  --motion-fast: ${motion.fast};`,
    `  --motion-base: ${motion.base};`,
    `  --motion-slow: ${motion.slow};`,
  ].join("\n");

  return `/* ============================================================
   AUTO-GENERIERT von scripts/build-tokens.ts — NICHT von Hand ändern.
   Quelle: tokens/primitive.ts + tokens/themes.ts (Designstudie §5.7).
   Neu generieren: npm run tokens:build
   ============================================================ */

@theme {
  /* Farb-Utilities zeigen auf Runtime-Variablen (--tk-*) → Theme-Wechsel
     überschreibt eine Ebene. UI nutzt nur diese semantischen Utilities. */
${colorUtilities}

  /* Schriftgrößen (§5.3) — Untergrenze 14px (caption). */
${fontSizeVars}

  /* Schriftfamilien (§5.3): humanistische Sans + echte Monospace. */
  --font-sans: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: "IBM Plex Mono", "JetBrains Mono", ui-monospace, "SFMono-Regular", monospace;

  /* Radius */
  --radius-sm: ${radius.sm};
  --radius-md: ${radius.md};
  --radius-lg: ${radius.lg};
}

/* Dark = Primärmodus (Halle). :root trägt zusätzlich die theme-agnostischen Maße. */
:root,
[data-theme="dark"] {
  color-scheme: dark;
${darkVars}
${scaleVars}
}

/* High-Contrast-Light (Streulicht) — eigene geprüfte Palette, keine naive Inversion. */
[data-theme="hc-light"] {
  color-scheme: light;
${lightVars}
}
`;
}

function main(): void {
  const css = buildCss();
  const check = process.argv.includes("--check");

  if (check) {
    if (!existsSync(OUT_PATH)) {
      console.error("❌ tokens.generated.css fehlt — `npm run tokens:build` ausführen.");
      process.exit(1);
    }
    const current = readFileSync(OUT_PATH, "utf8");
    if (current !== css) {
      console.error(
        "❌ tokens.generated.css weicht von der Token-Quelle ab — `npm run tokens:build` ausführen und committen.",
      );
      process.exit(1);
    }
    console.log("✅ tokens.generated.css ist synchron mit der Token-Quelle.");
    return;
  }

  mkdirSync(dirname(OUT_PATH), { recursive: true });
  writeFileSync(OUT_PATH, css, "utf8");
  console.log(`✅ Tokens generiert → ${OUT_PATH}`);
}

main();
