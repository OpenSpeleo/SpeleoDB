module.exports = {
    theme: {
        extend: {
            outline: {
                blue: '2px solid rgba(0, 112, 244, 0.5)',
            },
            fontFamily: {
                inter: ['Inter', 'sans-serif'],
            },
            fontSize: {
                xs: ['0.75rem', { lineHeight: '1.5' }],
                sm: ['0.875rem', { lineHeight: '1.5715' }],
                base: ['1rem', { lineHeight: '1.5', letterSpacing: '-0.01em' }],
                lg: ['1.125rem', { lineHeight: '1.5', letterSpacing: '-0.01em' }],
                xl: ['1.25rem', { lineHeight: '1.5', letterSpacing: '-0.01em' }],
                '2xl': ['1.5rem', { lineHeight: '1.33', letterSpacing: '-0.01em' }],
                '3xl': ['1.88rem', { lineHeight: '1.33', letterSpacing: '-0.01em' }],
                '4xl': ['2.25rem', { lineHeight: '1.25', letterSpacing: '-0.02em' }],
                '5xl': ['3rem', { lineHeight: '1.25', letterSpacing: '-0.02em' }],
                '6xl': ['3.75rem', { lineHeight: '1.2', letterSpacing: '-0.02em' }],
            },
            screens: {
                xs: '480px',
            },
            minWidth: {
                36: '9rem',
                44: '11rem',
                56: '14rem',
                60: '15rem',
                72: '18rem',
                80: '20rem',
            },
            maxWidth: {
                '8xl': '88rem',
                '9xl': '96rem',
            },
            spacing: {
                '128': '32rem',
            },
            width: {
                '128': '32rem', // Specifically adds it to the width utilities
            },
            zIndex: {
                60: '60',
            },
            borderWidth: {
                thin: "var(--border-width-thin)",
                medium: "var(--border-width-medium)",
                thick: "var(--border-width-thick)",
            },
            borderOpacity: {
                subtle: "var(--border-opacity-subtle)",
                medium: "var(--border-opacity-medium)",
                full: "var(--border-opacity-full)",
            },
        },
    },
    plugins: [
        require('@tailwindcss/forms')({ strategy: 'base' }),
        require('@tailwindcss/typography'),
    ],
};
