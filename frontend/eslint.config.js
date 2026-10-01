import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  { ignores: ['dist'] },
  js.configs.recommended,
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { document: 'readonly', window: 'readonly', setTimeout: 'readonly' },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: { ...reactHooks.configs.recommended.rules },
  },
];
