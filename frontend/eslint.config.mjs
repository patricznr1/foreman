// ============================================================
//  FOREMAN Frontend — eslint.config.mjs
//  Zweck: ESLint Flat Config auf Basis von next/core-web-vitals + next/typescript.
//  Architektur-Einordnung: Quality-Gate (npm run lint, §10 / GROUND_TRUTH §6).
// ============================================================
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({ baseDirectory: __dirname });

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "next-env.d.ts",
      "app/styles/tokens.generated.css",
      "public/**", // statische Assets (u. a. vendorter Draco-Decoder) — nicht zu linten
    ],
  },
  {
    rules: {
      // kein `any` (GROUND_TRUTH §6) — strikt erzwungen.
      "@typescript-eslint/no-explicit-any": "error",
      // Ungenutztes erlaubt mit _-Präfix (bewusst durchgereichte Parameter).
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
];

export default eslintConfig;
