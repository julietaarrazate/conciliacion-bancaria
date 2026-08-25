// ESLint sobrio: complementa a `tsc` (que ya cubre tipos) atrapando problemas
// reales sin ruido de estilo. Se apagan/bajan reglas que el repo viola a
// propósito o que tsc ya cubre, para que el CI marque cosas accionables.
module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  plugins: ['@typescript-eslint', 'react-hooks'],
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  env: { browser: true, es2022: true, node: true },
  parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
  ignorePatterns: ['dist/', 'node_modules/', '*.config.*', 'public/'],
  rules: {
    '@typescript-eslint/no-explicit-any': 'off', // el repo usa any a propósito en varios lugares
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    'no-empty': ['warn', { allowEmptyCatch: true }],
    'no-constant-condition': ['error', { checkLoops: false }],
    // rules-of-hooks: bug real (hooks condicionales). exhaustive-deps: warn —
    // el repo omite deps a propósito en varios useEffect (ver BUGS.md), no error.
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
  },
}
