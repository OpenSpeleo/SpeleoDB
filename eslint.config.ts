import { defineConfig } from 'eslint/config';
import tseslint from 'typescript-eslint';

export default defineConfig([
    {
        ignores: [
            '**/node_modules/**',
            '.venv/**',
            '.artifacts/**',
            '.cache/**',
            '**/dist/**',
            'frontend_private/static/private/ts/dist/**',
            'frontend_private/static/private/ts/vendors/**',
            'frontend_public/static/ts/dist/**',
            'frontend_public/static/ts/vendors/**',
            'speleodb/common/static/speleodb/vite/**',
            'staticfiles/**',
            '.railway/**'
        ]
    },
    {
        files: ['**/*.ts'],
        extends: [tseslint.configs.recommendedTypeChecked],
        linterOptions: { reportUnusedDisableDirectives: 'off' },
        languageOptions: {
            parserOptions: {
                project: [
                    './tsconfig.json',
                    './tsconfig.worker.json',
                    './tsconfig.development.json',
                ],
                tsconfigRootDir: import.meta.dirname,
            },
        },
        rules: {
            'no-undef': 'off',
            // Literal translation retains hoisting, declared async functions,
            // and unused legacy bindings; cleanup belongs to the refactor phase.
            'no-var': 'off',
            'prefer-const': 'off',
            '@typescript-eslint/no-unused-vars': 'off',
            '@typescript-eslint/require-await': 'off',
            // Existing catch/reject paths forward unknown failures unchanged.
            '@typescript-eslint/prefer-promise-reject-errors': ['error', { allowThrowingUnknown: true }],
        },
    },
    {
        files: [
            'frontend_common/security/html.ts',
            'frontend_private/static/private/ts/map_viewer/config.ts',
            'frontend_private/static/private/ts/map_viewer/utils.ts',
            'frontend_private/static/private/ts/map_viewer/map/depth.ts',
            'frontend_common/controllers/experiment-data.ts',
        ],
        rules: {
            // Escaping, permission normalization and section names preserve String(value), including
            // ordinary objects and throwing coercions; its contract tests cover both.
            '@typescript-eslint/no-base-to-string': 'off',
        },
    },
]);
