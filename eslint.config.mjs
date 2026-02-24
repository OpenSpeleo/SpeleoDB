import globals from 'globals';

const sharedGlobals = {
    ...globals.browser,
    ...globals.node,
    $: 'readonly',
    jQuery: 'readonly',
    AOS: 'readonly',
    Swiper: 'readonly',
    mapboxgl: 'readonly',
    Urls: 'readonly'
};

export default [
    {
        ignores: [
            '**/node_modules/**',
            '**/dist/**',
            'frontend_private/static/private/js/dist/**',
            'frontend_private/static/private/js/vendors/**',
            'frontend_public/static/js/dist/**',
            'frontend_public/static/js/vendors/**'
        ]
    },
    {
        files: [
            'frontend_private/static/private/js/**/*.js',
            'frontend_public/static/js/**/*.js'
        ],
        languageOptions: {
            ecmaVersion: 'latest',
            sourceType: 'module',
            globals: sharedGlobals
        },
        rules: {
            'no-undef': 'error'
        }
    },
    {
        files: [
            'frontend_public/static/js/**/*.test.js',
            'frontend_private/static/private/js/**/*.test.js'
        ],
        languageOptions: {
            globals: {
                ...sharedGlobals,
                describe: 'readonly',
                it: 'readonly',
                expect: 'readonly',
                beforeEach: 'readonly',
                afterEach: 'readonly',
                vi: 'readonly'
            }
        }
    }
];

