import { dirname, resolve } from "path"
import { fileURLToPath } from "url"

import { includeIgnoreFile } from "@eslint/compat"
import { FlatCompat } from "@eslint/eslintrc"

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const gitignorePath = resolve(__dirname, ".gitignore")

const compat = new FlatCompat({
  baseDirectory: __dirname,
})

const eslintConfig = [
  includeIgnoreFile(gitignorePath),
  ...compat.extends(
    "next/core-web-vitals",
    "next/typescript",
    "plugin:prettier/recommended"
  ),
  {
    // Keep eslint off static/generated assets and e2e test scripts. Linting the
    // minified JS/media in public/ made the CI lint step crawl for ~40 min and
    // then crash the stylish formatter with `RangeError: Invalid string length`
    // (output past V8's string limit), failing the build/deploy gate. The e2e/
    // playwright scripts keep runtime-style imports (require, placeholder env
    // vars) that are false positives under the app lint config.
    ignores: ["public/**", "public", "e2e/**", "e2e"],
  },
  {
    rules: {
      "import/consistent-type-specifier-style": ["error", "prefer-top-level"],
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-empty-object-type": "off",
      "@typescript-eslint/ban-ts-comment": "off",
      // The app leans on `any` for explicit visual/animation code (mock graphs,
      // canvas callbacks). Keep it visible as a warning rather than a build blocker.
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
    },
  },
]

export default eslintConfig
