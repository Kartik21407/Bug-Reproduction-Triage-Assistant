import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'node_modules'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      // Server state belongs in TanStack Query, and every request goes through
      // src/lib/api.ts. See section 6 of docs/conventions.md.
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: 'Call the API through src/lib/api.ts.' },
      ],
    },
  },
  {
    // The wrapper itself is the one place allowed to call fetch. Tests also
    // call it directly, to mock the network boundary.
    files: ['src/lib/api.ts', 'src/tests/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-globals': 'off',
    },
  },
);
