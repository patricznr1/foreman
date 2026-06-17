// ============================================================
//  FOREMAN Frontend — postcss.config.mjs
//  Zweck: Tailwind CSS v4 über das PostCSS-Plugin. Keine eigene tailwind.config —
//         das Theme kommt aus der generierten Token-CSS (tokens.generated.css),
//         gespeist aus der einzigen Token-Quelle (tokens/, Studie 5.7).
// ============================================================
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
