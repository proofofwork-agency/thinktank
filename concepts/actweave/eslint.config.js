import tseslint from "typescript-eslint";

const globals = {
  AbortController: "readonly",
  Buffer: "readonly",
  console: "readonly",
  fetch: "readonly",
  process: "readonly",
  setTimeout: "readonly",
  clearTimeout: "readonly",
  URL: "readonly",
  WebSocket: "readonly",
};

export default [
  {
    ignores: ["**/dist/**", "coverage/**", "**/node_modules/**", ".actweave/**"],
  },
  {
    files: ["**/*.{js,mjs}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals,
    },
    rules: {
      "no-duplicate-imports": "error",
      "no-irregular-whitespace": "error",
    },
  },
  {
    files: ["**/*.ts"],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        sourceType: "module",
      },
      globals,
    },
    plugins: {
      "@typescript-eslint": tseslint.plugin,
    },
    rules: {
      "no-duplicate-imports": "error",
      "no-irregular-whitespace": "error",
    },
  },
];
