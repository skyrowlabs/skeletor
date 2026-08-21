import js from '@eslint/js';
import globals from 'globals';

export default [
  js.configs.recommended,
  {
    files: ['**/*.{js,mjs,cjs}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
    },
    rules: {
      // Correctness only. Prettier owns formatting — a stylistic rule here and
      // a Prettier rule there will disagree, and the loser is whoever runs them
      // in the wrong order.
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      eqeqeq: ['error', 'always'],
      'no-var': 'error',
      'prefer-const': 'error',
    },
  },
  {
    ignores: ['node_modules/**', 'dist/**', 'build/**', 'tmp/**', '.venv/**'],
  },
];
