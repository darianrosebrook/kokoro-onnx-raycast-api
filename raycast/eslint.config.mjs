import js from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsparser from "@typescript-eslint/parser";
import globals from "globals";

export default [
  js.configs.recommended,
  // Raycast Plugin Configuration (browser-like environment)
  {
    files: [
      "src/speak-*.tsx",
      "src/types.ts",
      "src/types.d.ts",
      "src/mocks/**/*",
      "src/utils/**/*.ts",
      "src/utils/**/*.tsx",
    ],
    languageOptions: {
      parser: tsparser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        ...globals.browser,
        React: "readonly",
      },
    },
    plugins: {
      "@typescript-eslint": tseslint,
    },
    rules: {
      ...tseslint.configs.recommended.rules,
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "prefer-const": "error",
      "@typescript-eslint/no-empty-object-type": "off",
      "no-async-promise-executor": "off",
    },
  },
  // Node.js Configuration (daemon, tests, and Node.js utilities)
  {
    files: [
      "bin/**/*.{js,ts}",
      "test-*.js",
      "*.test.js",
      "src/test-*.tsx",
      "src/utils/**/*.test.ts",
      "src/utils/tts/streaming/audio-playback-daemon.ts",
      "src/utils/tts/streaming/adaptive-buffer-manager.ts",
    ],
    languageOptions: {
      parser: tsparser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
      },
      globals: {
        ...globals.node,
      },
    },
    plugins: {
      "@typescript-eslint": tseslint,
    },
    rules: {
      ...tseslint.configs.recommended.rules,
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "prefer-const": "error",
      "no-async-promise-executor": "off",
    },
  },
];
