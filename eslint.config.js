// Root-level ESLint flat config, covers both apps/web-app and
// apps/shared-ui - one config for the whole frontend workspace, matching
// how the project already treats apps/ as one unit (see .github/CODEOWNERS).
//
// This did not exist before - the frontend had zero automated checks
// beyond "does `npm run build` succeed" (real bugs a build doesn't catch:
// a useEffect with a stale/missing dependency, an unused variable left
// behind, a hooks-order violation). Added specifically so a PR from
// someone new to this codebase gets fast, mechanical, non-judgmental
// feedback before a human reviewer has to say the same things by hand.
//
// react-hooks/recommended catches the class of bug most likely for
// someone newer to React to introduce without realizing it (missing
// effect dependencies, calling a hook conditionally) - these are
// genuinely different from a hooks purism style-preference issue, they
// prevent hard-to-reproduce bugs (stale closures, state not updating
// when expected).
import js from "@eslint/js";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    // apps/contractor-app, apps/customer-app, apps/resource-owner-app are
    // deliberately kept as reference code, not deleted - see each one's
    // DEPRECATED.md and docs/adr/0002-single-unified-frontend-app.md.
    // They're already excluded from CI's build/test path
    // (.github/workflows/ci-frontend.yml only touches web-app/shared-ui) -
    // excluded here too for the same reason: linting code explicitly
    // marked "don't build here" produces noise, not signal.
    ignores: [
      "**/dist/**",
      "**/node_modules/**",
      "apps/contractor-app/**",
      "apps/customer-app/**",
      "apps/resource-owner-app/**",
    ],
  },
  {
    files: ["apps/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.es2022,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      react,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      // react-in-jsx-scope assumes React is in scope for JSX (the classic
      // transform) - this project uses the automatic JSX transform (see
      // apps/web-app/vite.config.js's @vitejs/plugin-react default), so
      // "React must be in scope" is a false positive here.
      "react/react-in-jsx-scope": "off",
      // prop-types is off, not misconfigured: this codebase has never
      // used PropTypes (no TypeScript either) - turning this rule on
      // would surface 100+ pre-existing "errors" on the very first run,
      // none caused by anything a new contributor wrote, which defeats
      // the point of a linter as an onboarding tool (signal buried in
      // noise). If this project adopts TypeScript or PropTypes later,
      // that's a deliberate, separate decision - not a side effect of
      // this config file.
      "react/prop-types": "off",
      // Vite's own recommended rule for its Fast Refresh feature - flags
      // a file that mixes a component export with other exports, which
      // breaks hot-reload in dev. allowConstantExport: true permits the
      // common, harmless case of exporting a constant alongside a
      // component.
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // Not an error: unused function args are common in this codebase's
      // event-handler signatures where only some args are needed, and
      // flagging every one as an error (vs. a warning) would generate
      // more noise than signal for a first-time contributor. Unused
      // top-level variables/imports still warn (not silenced) below.
      "no-unused-vars": ["warn", { args: "none" }],
    },
    settings: {
      react: { version: "detect" },
    },
  },
  {
    // Node-context config files (this file itself, vite.config.js) run
    // under Node, not the browser - different global set.
    files: ["**/*.config.js"],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
];
