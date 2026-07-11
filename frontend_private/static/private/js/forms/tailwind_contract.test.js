import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

import tailwindcss from '@tailwindcss/vite';
import { build as viteBuild } from 'vite';

const ROOT = process.cwd();
const CSS_EXTENSIONS = new Set(['.css']);
const HTML_EXTENSIONS = new Set(['.html']);
const JAVASCRIPT_EXTENSIONS = new Set(['.js']);

const read = relativePath => fs.readFileSync(path.join(ROOT, relativePath), 'utf8');
const readJson = relativePath => JSON.parse(read(relativePath));
const digest = relativePath => createHash('sha256').update(read(relativePath)).digest('hex');

const listFiles = (relativePath, recursive, extensions) => {
    const absolutePath = path.join(ROOT, relativePath);
    const entries = fs.readdirSync(absolutePath, { withFileTypes: true })
        .sort((left, right) => left.name.localeCompare(right.name));
    const files = [];

    for (const entry of entries) {
        if (entry.isDirectory()) {
            if (recursive) {
                files.push(...listFiles(path.join(relativePath, entry.name), true, extensions));
            }
            continue;
        }

        if (extensions.has(path.extname(entry.name))) {
            files.push(path.join(relativePath, entry.name));
        }
    }

    return files;
};

const sourceDirectives = css => [...css.matchAll(/^@source\s+"([^"]+)";/gm)].map(match => match[1]);

const expectInOrder = (text, markers) => {
    let previousIndex = -1;

    for (const marker of markers) {
        const index = text.indexOf(marker, previousIndex + 1);
        expect(index, `Missing or out-of-order marker: ${marker}`).toBeGreaterThan(previousIndex);
        previousIndex = index;
    }
};

const cssVariables = css => Object.fromEntries(
    [...css.matchAll(/^\s*(--[a-z0-9-]+):\s*([^;]+);/gim)]
        .map(match => [match[1], match[2].trim()]),
);

const escapeRegExp = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const cssRuleBodies = (css, selector) => [
    ...css.matchAll(new RegExp(`${escapeRegExp(selector)}\\{([^{}]*)\\}`, 'g')),
].map(match => match[1]);

const writeMirrorFile = (mirrorRoot, relativePath, contents) => {
    const absolutePath = path.join(mirrorRoot, relativePath);
    fs.mkdirSync(path.dirname(absolutePath), { recursive: true });
    fs.writeFileSync(absolutePath, contents);
};

const compile = async (inputPath, cwd) => {
    const result = await viteBuild({
        root: cwd,
        configFile: false,
        logLevel: 'silent',
        plugins: [tailwindcss()],
        build: {
            write: false,
            minify: true,
            cssMinify: 'lightningcss',
            cssTarget: ['chrome111', 'firefox128', 'safari16.4'],
            rolldownOptions: { input: inputPath },
        },
    });
    const output = Array.isArray(result)
        ? result.flatMap(environment => environment.output)
        : result.output;
    const cssAssets = output.filter(
        asset => asset.type === 'asset' && asset.fileName.endsWith('.css'),
    );
    expect(cssAssets).toHaveLength(1);
    return String(cssAssets[0].source);
};

const compileOutput = relativeInput => compile(path.join(ROOT, relativeInput), ROOT);

const compileSourceMirror = async () => {
    const mirrorRoot = fs.mkdtempSync(path.join(ROOT, '.tailwind-contract-'));

    try {
        fs.cpSync(path.join(ROOT, 'tailwind_css'), path.join(mirrorRoot, 'tailwind_css'), { recursive: true });

        const sources = {
            'frontend_public/templates/page.html': '<div class="z-[101] site-h1 site-btn site-form-input text-base text-3xl font-inter tracking-tight animate-float prose outline-blue max-w-9xl"></div>',
            'frontend_public/templates/footer.html': '<footer class="z-[102]"></footer>',
            'frontend_public/static/js/public.js': "const runtimeClasses = ['z-[103]'];",
            'frontend_public/static/js/nested/excluded.js': "const excluded = 'z-[191]';",
            'frontend_public/templatetags/people_tags.py': "PUBLIC_TAG_CLASS = 'z-[104]'",
            'frontend_private/templates/page.html': '<div class="z-[201] text-base text-3xl font-inter w-128 min-w-36 max-w-9xl border-thin xs:block prose outline-blue animate-float"></div>',
            'frontend_private/static/private/js/private.js': "const runtimeClasses = ['z-[202]'];",
            'frontend_private/static/private/js/forms/excluded.js': "const excluded = 'z-[291]';",
            'frontend_private/static/private/js/map_viewer/deep/runtime.js': "const runtimeClasses = ['z-[203]'];",
            'speleodb/surveys/templatetags/project_types.py': "PRIVATE_TAG_CLASS = 'z-[204]'",
            'speleodb/surveys/other.py': "EXCLUDED_CLASS = 'z-[292]'",
        };

        for (const [relativePath, contents] of Object.entries(sources)) {
            writeMirrorFile(mirrorRoot, relativePath, contents);
        }

        return {
            unifiedOutput: await compile(
                path.join(mirrorRoot, 'tailwind_css/style.css'),
                mirrorRoot,
            ),
            privateOutput: await compile(
                path.join(mirrorRoot, 'tailwind_css/private/style.css'),
                mirrorRoot,
            ),
        };
    } finally {
        fs.rmSync(mirrorRoot, { recursive: true, force: true });
    }
};

const leafRuleSignatures = source => {
    const css = source.replace(/\/\*[^]*?\*\//g, '');
    const signatures = [];

    const collect = text => {
        let cursor = 0;

        while (cursor < text.length) {
            const openingBrace = text.indexOf('{', cursor);
            if (openingBrace === -1) {
                return;
            }

            const header = text.slice(cursor, openingBrace).replace(/^\s*;+/, '').trim();
            let depth = 1;
            let closingBrace = openingBrace + 1;
            while (closingBrace < text.length && depth > 0) {
                if (text[closingBrace] === '{') {
                    depth += 1;
                } else if (text[closingBrace] === '}') {
                    depth -= 1;
                }
                closingBrace += 1;
            }

            const body = text.slice(openingBrace + 1, closingBrace - 1);
            let bodyDepth = 0;
            let hasNestedBlock = false;
            for (const character of body) {
                if (character === '{' && bodyDepth === 0) {
                    hasNestedBlock = true;
                    break;
                }
                if (character === '{') {
                    bodyDepth += 1;
                } else if (character === '}') {
                    bodyDepth -= 1;
                }
            }

            if (hasNestedBlock) {
                collect(body);
            } else if (header !== '') {
                signatures.push(`${header}{${body.replace(/\s+/g, ' ').trim()}}`);
            }
            cursor = closingBrace;
        }
    };

    collect(css);
    return signatures;
};

const expectRuleSubsequence = (referenceCss, unifiedCss) => {
    const declarationSupersets = [
        '*,:before,:after,::backdrop{--tw-',
        ':root,:host{--',
    ];
    const referenceRules = leafRuleSignatures(referenceCss)
        .filter(rule => !declarationSupersets.some(prefix => rule.startsWith(prefix)))
        .filter(rule => !rule.startsWith('@property --tw-'));
    const unifiedRules = leafRuleSignatures(unifiedCss);
    let unifiedIndex = 0;

    for (const referenceRule of referenceRules) {
        const foundIndex = unifiedRules.indexOf(referenceRule, unifiedIndex);
        expect(foundIndex, `Unified output changed or omitted: ${referenceRule.slice(0, 160)}`)
            .toBeGreaterThanOrEqual(unifiedIndex);
        unifiedIndex = foundIndex + 1;
    }
};

const compilerOwnedSourceFiles = () => [
    ...listFiles('frontend_public/templates', true, HTML_EXTENSIONS),
    ...listFiles('frontend_public/static/js', false, JAVASCRIPT_EXTENSIONS),
    'frontend_public/templatetags/people_tags.py',
    ...listFiles('frontend_private/templates', true, HTML_EXTENSIONS),
    ...listFiles('frontend_private/static/private/js', false, JAVASCRIPT_EXTENSIONS),
    ...listFiles('frontend_private/static/private/js/map_viewer', true, JAVASCRIPT_EXTENSIONS),
    'speleodb/surveys/templatetags/project_types.py',
];

const candidateSourceText = (relativePath, source) => {
    if (relativePath.endsWith('.html')) {
        return source
            .replace(/<!--[^]*?-->/g, '')
            .replace(/<style\b[^>]*>[^]*?<\/style>/gi, '')
            .replace(/\sstyle\s*=\s*(?:"[^"]*"|'[^']*')/gi, '');
    }

    if (relativePath.endsWith('.js')) {
        return source
            .replace(/\/\*[^]*?\*\//g, '')
            .replace(/^\s*\/\/.*$/gm, '');
    }

    return source.replace(/^\s*#.*$/gm, '');
};

describe('Tailwind v4 single-bundle contract', () => {
    const packageJson = readJson('package.json');
    const packageLock = readJson('package-lock.json');
    const v3Contract = readJson('frontend_private/static/private/js/forms/fixtures/tailwind-v3.4.19-contract.json');
    const entryCss = read('tailwind_css/style.css');
    const privateCss = read('tailwind_css/private/style.css');
    const publicComponents = read('tailwind_css/public/components.css');
    const privateComponents = read('tailwind_css/private/additional-styles/utility-patterns.css');
    const privateCustomCss = read('frontend_private/static/private/css/custom.css');
    const gitViewTemplate = read('frontend_private/templates/pages/project/git_view.html');
    const designSystemCss = read('tailwind_css/shared/design-system.css');
    it('keeps compiler dependencies, lockfile, and install-script graph aligned', () => {
        const requiredPackages = [
            '@tailwindcss/forms',
            '@tailwindcss/typography',
            '@tailwindcss/vite',
            'tailwindcss',
            'vite',
        ];

        expect(packageLock.packages[''].devDependencies).toEqual(packageJson.devDependencies);

        for (const packageName of requiredPackages) {
            expect(packageJson.devDependencies).toHaveProperty(packageName);
            const lockNode = packageLock.packages[`node_modules/${packageName}`];
            expect(lockNode, `Missing package-lock node for ${packageName}`).toBeDefined();
            expect(lockNode.integrity).toMatch(/^sha512-/);
        }

        const lockedInstallScripts = Object.entries(packageLock.packages)
            .filter(([, metadata]) => metadata.hasInstallScript)
            .map(([lockPath, metadata]) => `${lockPath.replace(/^node_modules\//, '')}@${metadata.version}`)
            .sort();
        expect(Object.keys(packageJson.allowScripts).sort()).toEqual(lockedInstallScripts);
    });

    it('exposes exactly one neutral build, watch, and pre-commit interface', () => {
        expect(packageJson.scripts['build:assets']).toBe('vite build --mode production');
        expect(packageJson.scripts.dev).toBe('vite build --watch --mode development');
        expect(packageJson.scripts['pre-commit']).toBe('npm run build');

        for (const obsoleteName of [
            'build:tailwind:public',
            'build:tailwind:private',
            'dev:tailwind:public',
            'dev:tailwind:private',
            'pre-commit:tailwind:public',
            'pre-commit:tailwind:private',
            'build:tailwind',
            'dev:tailwind',
            'pre-commit:tailwind',
            'build:esbuild',
            'build:esbuild:private',
            'build:esbuild:public',
            'dev:esbuild:private',
            'dev:esbuild:public',
            'pre-commit:esbuild',
        ]) {
            expect(packageJson.scripts[obsoleteName]).toBeUndefined();
        }

        expect(packageJson.scripts.build).toBe('npm run build:clean && npm run build:assets');
        expect(packageJson.scripts.start).toBe('npm run dev');
        expect(packageJson.scripts['build:clean']).toContain('speleodb/common/static/speleodb/vite');
        expect(packageJson.scripts['build:clean']).toContain('frontend_public/static/css/style.css');
        expect(packageJson.scripts['build:clean']).toContain('frontend_private/static/private/css/style.css');
        expect(Object.values(packageJson.scripts).join('\n')).not.toContain(' -c ');
        expect(fs.existsSync(path.join(ROOT, 'scripts/tailwind-watch.mjs'))).toBe(false);
        expect(fs.existsSync(path.join(ROOT, 'vite.config.mjs'))).toBe(true);
    });

    it('uses one production entrypoint while leaving the private reference byte-exact', () => {
        expect(digest('tailwind_css/private/style.css')).toBe(
            '44daabdbfa3b6b121750f7531b3b0570965e180398101f17e2a263609c614734',
        );
        expect(digest('tailwind_css/private/additional-styles/utility-patterns.css')).toBe(
            '29990d20df6e3c8425819eef2558663958eeddd7164d727b32a4e8d0eb17b595',
        );
        expect(digest('tailwind_css/private/additional-styles/flatpickr.css')).toBe(
            '876a74a84e774349c3c8bcdb5cb7d83f49c9b876d3d263f4f819b5286be4fb44',
        );

        expect(fs.existsSync(path.join(ROOT, 'tailwind_css/style.css'))).toBe(true);
        expect(fs.existsSync(path.join(ROOT, 'tailwind_css/public/style.css'))).toBe(false);
        expect(fs.existsSync(path.join(ROOT, 'tailwind_css/public/tailwind.config.js'))).toBe(false);
        expect(fs.existsSync(path.join(ROOT, 'tailwind_css/private/tailwind.config.js'))).toBe(false);
        expectInOrder(entryCss, [
            "@import './private/style.css';",
            "@import './public/components.css' layer(components);",
            '@theme inline',
            '@source "../frontend_public/templates/**/*.html";',
            '@source "../frontend_public/static/js/*.js";',
            '@source "../frontend_public/templatetags/people_tags.py";',
        ]);
        expect(entryCss).not.toMatch(/--text-(?:base|lg|xl|[2-7]xl):/);
        expect(entryCss).not.toMatch(/--tracking-/);
    });

    it('freezes private import, source, layer, theme, and variant order', () => {
        expectInOrder(privateCss, [
            "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=fallback');",
            "@import 'tailwindcss' source(none);",
            "@import '../shared/design-system.css';",
            '@theme inline',
            "@import './additional-styles/utility-patterns.css' layer(components);",
            "@import './additional-styles/flatpickr.css' layer(components);",
            '@source "../../frontend_private/templates/**/*.html";',
            '@source "../../frontend_public/templates/footer.html";',
            '@source "../../frontend_private/static/private/js/*.js";',
            '@source "../../frontend_private/static/private/js/map_viewer/**/*.js";',
            '@source "../../speleodb/surveys/templatetags/project_types.py";',
            '@custom-variant dark (&:is(.dark *));',
            '@custom-variant hover (&:hover);',
            '@custom-variant group-hover (.group:hover &);',
            '@custom-variant sidebar-expanded (.sidebar-expanded &);',
            '@theme',
            '@layer base',
            '@layer utilities',
        ]);
        expect(sourceDirectives(entryCss)).toEqual([
            '../frontend_public/templates/**/*.html',
            '../frontend_public/static/js/*.js',
            '../frontend_public/templatetags/people_tags.py',
            '../frontend_common/**/*.js',
            '../frontend_common/**/*.css',
        ]);
        expect(sourceDirectives(privateCss)).toEqual([
            '../../frontend_private/templates/**/*.html',
            '../../frontend_public/templates/footer.html',
            '../../frontend_private/static/private/js/*.js',
            '../../frontend_private/static/private/js/map_viewer/**/*.js',
            '../../speleodb/surveys/templatetags/project_types.py',
        ]);
    });

    it('uses one CSS-native plugin foundation without legacy configuration', () => {
        const productionCss = listFiles('tailwind_css', true, CSS_EXTENSIONS);
        const allCss = productionCss.map(read).join('\n');

        expect(allCss).not.toContain('@config');
        expect(allCss.match(/@plugin "@tailwindcss\/forms"/g)).toHaveLength(1);
        expect(allCss.match(/@plugin "@tailwindcss\/typography"/g)).toHaveLength(1);
        expect(designSystemCss).toMatch(
            /@plugin "@tailwindcss\/forms"\s*\{\s*strategy:\s*"base";\s*\}/m,
        );
        expect(designSystemCss).toContain('--font-inter: Inter, sans-serif;');
        expect(designSystemCss).toContain('color-scheme: dark;');
        expect(fs.existsSync(path.join(ROOT, 'tailwind_css/shared/v3-compat.css'))).toBe(false);

        for (const relativePath of productionCss) {
            expect(read(relativePath), `${relativePath} exposes a migration-version name`)
                .not.toMatch(/(?:^|[^a-z0-9])v3-/im);
        }
    });

    it('compiles the union source set and excludes unsupported nested trees', async () => {
        const { unifiedOutput } = await compileSourceMirror();

        for (const value of [101, 102, 103, 104, 201, 202, 203, 204]) {
            expect(unifiedOutput, `Unified build omitted z-[${value}]`).toContain(`z-index:${value}`);
        }
        for (const value of [191, 291, 292]) {
            expect(unifiedOutput, `Unified build leaked z-[${value}]`).not.toContain(`z-index:${value}`);
        }

        expect(cssRuleBodies(unifiedOutput, '.site-h1')).not.toHaveLength(0);
        expect(cssRuleBodies(unifiedOutput, '.site-btn')).not.toHaveLength(0);
        expect(cssRuleBodies(unifiedOutput, '.site-form-input')).not.toHaveLength(0);
        expect(cssRuleBodies(unifiedOutput, '.animate-float').join(';'))
            .toContain('animation:2s ease-in-out infinite float');
        expect(cssRuleBodies(unifiedOutput, '.outline-blue').join(';'))
            .toContain('outline:2px solid #0070f480');
        expect(cssRuleBodies(unifiedOutput, '.max-w-9xl').join(';')).toContain('max-width:96rem');
    }, 30_000);

    it('preserves every compiled private leaf rule and its relative order', async () => {
        const { unifiedOutput, privateOutput } = await compileSourceMirror();
        expectRuleSubsequence(privateOutput, unifiedOutput);

        for (const supersetSelector of ['*,:before,:after,::backdrop', ':root,:host']) {
            const privateDeclarations = cssRuleBodies(privateOutput, supersetSelector).join(';');
            const unifiedDeclarations = cssRuleBodies(unifiedOutput, supersetSelector).join(';');
            for (const declaration of privateDeclarations.split(';').filter(Boolean)) {
                expect(unifiedDeclarations, `Unified ${supersetSelector} omitted ${declaration}`)
                    .toContain(declaration);
            }
        }

        const unifiedRules = new Set(leafRuleSignatures(unifiedOutput));
        const privatePropertyRules = leafRuleSignatures(privateOutput)
            .filter(rule => rule.startsWith('@property --tw-'));
        for (const propertyRule of privatePropertyRules) {
            expect(unifiedRules, `Unified output omitted ${propertyRule}`).toContain(propertyRule);
        }
    }, 30_000);

    it('uses private typography and namespaced public components without selector collisions', async () => {
        const unifiedOutput = await compileOutput('tailwind_css/style.css');
        const baseRules = cssRuleBodies(unifiedOutput, '.text-base').join(';');
        const threeXlRules = cssRuleBodies(unifiedOutput, '.text-3xl').join(';');

        expect(baseRules).toContain('font-size:1rem');
        expect(baseRules).toContain('line-height:var(--tw-leading,1.5)');
        expect(baseRules).toContain('letter-spacing:var(--tw-tracking,-.01em)');
        expect(threeXlRules).toContain('font-size:1.88rem');
        expect(threeXlRules).toContain('line-height:var(--tw-leading,1.33)');

        expect(publicComponents).not.toMatch(
            /(?:^|\n)\s*\.(?:btn(?:-(?:sm|lg|xs))?|h[1-5]|form-(?:input|textarea|multiselect|select|checkbox|radio))\b/m,
        );
        expect(cssRuleBodies(unifiedOutput, '.site-btn,.site-btn-sm').join(';'))
            .toContain('border-radius:var(--radius-full)');
        expect(cssRuleBodies(unifiedOutput, '.site-form-input').join(';'))
            .toContain('background-color:var(--color-slate-800)');
        expect(cssRuleBodies(unifiedOutput, '.site-shadow-sm-purple-25').join(';'))
            .toContain('0 1px 2px -1px var(--color-srgb-purple-500-25)');
        expect(read('frontend_public/templates/pages/home.html'))
            .not.toContain('shadow-sm shadow-srgb-purple-500-25');
        expect(read('frontend_public/templates/snippets/welcome_modal.html'))
            .not.toContain('p-6 sm:p-8 md:p-12');

        const allowedPrivateComponents = new Map([
            ['frontend_public/templates/pages/gis_view_map.html', new Set(['btn'])],
            ['frontend_public/templates/snippets/welcome_modal.html', new Set(['btn'])],
        ]);
        const conflictingTokens = new Set([
            'btn', 'btn-sm', 'btn-lg', 'btn-xs',
            'h1', 'h2', 'h3', 'h4', 'h5',
            'form-input', 'form-textarea', 'form-multiselect', 'form-select', 'form-checkbox', 'form-radio',
        ]);

        for (const relativePath of listFiles('frontend_public/templates', true, HTML_EXTENSIONS)) {
            const allowed = allowedPrivateComponents.get(relativePath) ?? new Set();
            const classValues = [...candidateSourceText(relativePath, read(relativePath))
                .matchAll(/\bclass\s*=\s*["']([^"']*)["']/g)]
                .map(match => match[1]);
            for (const classValue of classValues) {
                for (const token of classValue.split(/\s+/)) {
                    if (conflictingTokens.has(token)) {
                        expect(allowed, `${relativePath} uses unnamespaced ${token}`).toContain(token);
                    }
                }
            }
        }
    }, 30_000);

    it('freezes every v3 palette value and relevant default token', () => {
        const actualVariables = cssVariables(designSystemCss);
        const expectedPalette = {
            '--color-black': v3Contract.palette.black,
            '--color-white': v3Contract.palette.white,
        };

        for (const [family, serializedColors] of Object.entries(v3Contract.palette)) {
            if (family === 'black' || family === 'white') {
                continue;
            }

            const colors = serializedColors.split(' ');
            expect(colors, `${family} must define every v3 shade`).toHaveLength(v3Contract.shades.length);
            v3Contract.shades.forEach((shade, index) => {
                expectedPalette[`--color-${family}-${shade}`] = colors[index];
            });
        }

        const paletteNames = Object.keys(actualVariables)
            .filter(name => /^--color-(?:black|white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)(?:-|$)/.test(name))
            .sort();
        expect(paletteNames).toEqual(Object.keys(expectedPalette).sort());
        expect(Object.fromEntries(paletteNames.map(name => [name, actualVariables[name]]))).toEqual(expectedPalette);

        for (const [name, value] of Object.entries(v3Contract.defaults)) {
            expect(actualVariables[name], `${name} diverged from Tailwind 3.4.19`).toBe(value);
        }
    });

    it('inspects all compiler-owned runtime contexts for removed candidates and private variables', () => {
        const removedCandidates = [
            /(?:^|\s)(?:[A-Za-z0-9_-]+:)*(?:bg|text|border|divide|ring)-opacity-\d+(?=\s|$)/m,
            /(?:^|\s)(?:[A-Za-z0-9_-]+:)*flex-(?:shrink|grow)(?:-\d+)?(?=\s|$)/m,
            /(?:^|\s)(?:[A-Za-z0-9_-]+:)*overflow-ellipsis(?=\s|$)/m,
            /(?:^|\s)(?:[A-Za-z0-9_-]+:)*bg-gradient-to-[trbl]{1,2}(?=\s|$)/m,
            /(?:^|\s)(?:before:hover|after:group-hover|hover:prose-a):/m,
            /(?:^|\s)(?:[A-Za-z0-9_-]+:)*(?:space-[xy]-(?:reverse|\d)|divide-y)(?=\s|$)/m,
            /(?:^|\s)(?:[A-Za-z0-9_-]+:)*max-w-13(?=\s|$)/m,
            /(?:^|\s)(?:[A-Za-z0-9_-]+:)*(?:bg|text|border|ring|from|via|to|decoration|shadow)-(?:slate|gray|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black|white)-\d+\/\d+(?=\s|$)/m,
            /(?:^|\s)(?:[A-Za-z0-9_-]+:)*text-transparent(?=\s|$)/m,
        ];

        for (const relativePath of compilerOwnedSourceFiles()) {
            const source = candidateSourceText(relativePath, read(relativePath));
            for (const candidate of removedCandidates) {
                expect(source, `${relativePath} contains ${candidate}`).not.toMatch(candidate);
            }
        }

        const processedCss = [
            ...listFiles('tailwind_css', true, CSS_EXTENSIONS),
            ...listFiles('frontend_public', true, CSS_EXTENSIONS),
            ...listFiles('frontend_private', true, CSS_EXTENSIONS),
        ].filter(relativePath => ![
            'tailwind_css/shared/design-system.css',
            'frontend_public/static/css/style.css',
            'frontend_private/static/private/css/style.css',
        ].includes(relativePath) && !relativePath.includes('/vendors/'));

        for (const relativePath of [...new Set([...compilerOwnedSourceFiles(), ...processedCss])].sort()) {
            expect(read(relativePath), `${relativePath} couples to Tailwind internals`)
                .not.toMatch(/--tw-[a-z0-9-]+/i);
        }
    });

    it('freezes the single-asset production stylesheet compositions', () => {
        const publicBase = read('frontend_public/templates/base.html');
        const privateBase = read('frontend_private/templates/base_private.html');
        const publicMap = read('frontend_public/templates/pages/gis_view_map.html');
        const privateMap = read('frontend_private/templates/pages/map_viewer.html');
        const ariane = read('frontend_public/templates/webviews/ariane.html');
        const allTemplates = listFiles('frontend_public/templates', true, HTML_EXTENSIONS)
            .concat(listFiles('frontend_private/templates', true, HTML_EXTENSIONS))
            .map(read)
            .join('\n');

        expectInOrder(publicBase, [
            "{% static 'css/vendors/aos.css' %}",
            'https://cdnjs.cloudflare.com/ajax/libs/aos/3.0.0-beta.6/aos.css',
            'https://fonts.googleapis.com/css2?family=Inter:wght@800&amp;display=fallback',
            "{% vite_styles 'style-app' 'style-public-shell' %}",
            '{% block extra_css %}',
        ]);
        expectInOrder(privateBase, [
            "{% vite_styles 'style-app' 'style-private-shell' %}",
            "{% vite_styles 'style-template-frontend-private-templates-base-private' %}",
            '{% block extra_css %}',
        ]);
        expectInOrder(publicMap, [
            "{% vite_styles 'style-private-shell' 'style-shared-modal' 'style-map-viewer' %}",
            'https://api.mapbox.com/mapbox-gl-js/v3.12.0/mapbox-gl.css',
        ]);
        expect(publicMap).not.toContain('private/css/style.css');
        expect(ariane).toContain("{% vite_styles 'style-app' %}");
        expectInOrder(privateMap, [
            'https://api.mapbox.com/mapbox-gl-js/v3.12.0/mapbox-gl.css',
            "{% vite_styles 'style-shared-modal' 'style-map-viewer' %}",
        ]);
        expect(allTemplates).not.toContain("{% static 'css/style.css' %}");
        expect(allTemplates).not.toContain("{% static 'private/css/style.css' %}");
    });

    it('retains private component cascade and the clean Git-browser surface', async () => {
        const unifiedOutput = await compileOutput('tailwind_css/style.css');
        const buttonSelector = '.btn,.btn-lg,.btn-sm,.btn-xs';
        const formSelector = '.form-input,.form-textarea,.form-multiselect,.form-select';
        const buttonRules = cssRuleBodies(unifiedOutput, buttonSelector).join(';');
        const formRules = cssRuleBodies(unifiedOutput, formSelector).join(';');

        for (const [selector, rules] of [[buttonSelector, buttonRules], [formSelector, formRules]]) {
            expect(rules, `Unified build omitted ${selector}`).not.toBe('');
            expect(rules, `${selector} lost the v3 line-height`).toContain('line-height:1.25rem');
            expect(rules, `${selector} leaks inherited leading state`).not.toMatch(/--tw-leading\s*:/);
        }

        expect(gitViewTemplate.match(/bg-linear-to-b\/srgb from-white to-gray-100/g)).toHaveLength(2);
        expect(privateComponents).not.toMatch(/\.git_btn\s*{/);
        expect(privateCustomCss).not.toMatch(/\.git_btn\s*{/);
        expect(unifiedOutput).toContain('.bg-linear-to-b\\/srgb');
        expect(unifiedOutput).toContain('.from-white');
        expect(unifiedOutput).toContain('.to-gray-100');
        expect(unifiedOutput).toContain('.rounded-full');
        expect(unifiedOutput).toContain('.cursor-pointer');
        expect(unifiedOutput).not.toMatch(/\.git_btn\s*\{[^}]*\bbackground(?:-image)?\s*:/);
    }, 30_000);
});
