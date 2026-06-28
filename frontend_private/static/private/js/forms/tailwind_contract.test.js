import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const TAILWIND_CLI = path.join(ROOT, 'node_modules', '.bin', 'tailwindcss');
const CSS_EXTENSIONS = new Set(['.css']);
const HTML_EXTENSIONS = new Set(['.html']);
const JAVASCRIPT_EXTENSIONS = new Set(['.js']);

const read = relativePath => fs.readFileSync(path.join(ROOT, relativePath), 'utf8');
const readJson = relativePath => JSON.parse(read(relativePath));

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

const compile = (inputPath, outputPath, cwd) => {
    execFileSync(TAILWIND_CLI, ['-i', inputPath, '-o', outputPath, '--minify'], {
        cwd,
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'pipe'],
    });
};

const compileSourceMirror = () => {
    const mirrorRoot = fs.mkdtempSync(path.join(ROOT, '.tailwind-contract-'));

    try {
        fs.cpSync(path.join(ROOT, 'tailwind_css'), path.join(mirrorRoot, 'tailwind_css'), { recursive: true });

        const sources = {
            'frontend_public/templates/page.html': '<div class="z-[101]"></div>',
            'frontend_public/templates/footer.html': '<footer class="z-[102]"></footer>',
            'frontend_public/static/js/public.js': "const runtimeClasses = ['z-[103]'];",
            'frontend_public/static/js/nested/excluded.js': "const excluded = 'z-[191]';",
            'frontend_public/templatetags/people_tags.py': "PUBLIC_TAG_CLASS = 'z-[104]'",
            'frontend_private/templates/page.html': '<div class="z-[201]"></div>',
            'frontend_private/static/private/js/private.js': "const runtimeClasses = ['z-[202]'];",
            'frontend_private/static/private/js/forms/excluded.js': "const excluded = 'z-[291]';",
            'frontend_private/static/private/js/map_viewer/deep/runtime.js': "const runtimeClasses = ['z-[203]'];",
            'speleodb/surveys/templatetags/project_types.py': "PRIVATE_TAG_CLASS = 'z-[204]'",
            'speleodb/surveys/other.py': "EXCLUDED_CLASS = 'z-[292]'",
        };

        for (const [relativePath, contents] of Object.entries(sources)) {
            writeMirrorFile(mirrorRoot, relativePath, contents);
        }

        const publicOutputPath = path.join(mirrorRoot, 'public.css');
        const privateOutputPath = path.join(mirrorRoot, 'private.css');
        compile(path.join(mirrorRoot, 'tailwind_css/public/style.css'), publicOutputPath, mirrorRoot);
        compile(path.join(mirrorRoot, 'tailwind_css/private/style.css'), privateOutputPath, mirrorRoot);

        return {
            publicOutput: fs.readFileSync(publicOutputPath, 'utf8'),
            privateOutput: fs.readFileSync(privateOutputPath, 'utf8'),
        };
    } finally {
        fs.rmSync(mirrorRoot, { recursive: true, force: true });
    }
};

const compileCleanPrivateOutput = () => {
    const outputRoot = fs.mkdtempSync(path.join(ROOT, '.tailwind-contract-'));

    try {
        const outputPath = path.join(outputRoot, 'private.css');
        compile(path.join(ROOT, 'tailwind_css/private/style.css'), outputPath, ROOT);
        return fs.readFileSync(outputPath, 'utf8');
    } finally {
        fs.rmSync(outputRoot, { recursive: true, force: true });
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

describe('Tailwind v4 build contract', () => {
    const packageJson = readJson('package.json');
    const packageLock = readJson('package-lock.json');
    const v3Contract = readJson('frontend_private/static/private/js/forms/fixtures/tailwind-v3.4.19-contract.json');
    const publicCss = read('tailwind_css/public/style.css');
    const privateCss = read('tailwind_css/private/style.css');
    const publicConfig = read('tailwind_css/public/tailwind.config.js');
    const privateConfig = read('tailwind_css/private/tailwind.config.js');
    const privateComponents = read('tailwind_css/private/additional-styles/utility-patterns.css');
    const privateCustomCss = read('frontend_private/static/private/css/custom.css');
    const gitViewTemplate = read('frontend_private/templates/pages/project/git_view.html');
    const designSystemCss = read('tailwind_css/shared/design-system.css');

    it('pins the compiler, CLI, and plugins to the approved package graph', () => {
        const expectedPackages = {
            '@tailwindcss/cli': '4.3.1',
            '@tailwindcss/forms': '0.5.11',
            '@tailwindcss/typography': '0.5.20',
            tailwindcss: '4.3.1',
        };

        expect(packageJson.devDependencies).toMatchObject(expectedPackages);
        expect(packageLock.lockfileVersion).toBe(3);
        expect(packageLock.packages[''].devDependencies).toEqual(packageJson.devDependencies);

        for (const [packageName, version] of Object.entries(expectedPackages)) {
            const lockNode = packageLock.packages[`node_modules/${packageName}`];
            expect(lockNode, `Missing package-lock node for ${packageName}`).toBeDefined();
            expect(lockNode.version).toBe(version);
            expect(lockNode.resolved).toContain(`-${version}.tgz`);
            expect(lockNode.integrity).toMatch(/^sha512-/);
        }

        const cliNode = packageLock.packages['node_modules/@tailwindcss/cli'];
        expect(cliNode.dependencies).toMatchObject({
            '@parcel/watcher': '2.5.1',
            '@tailwindcss/node': '4.3.1',
            '@tailwindcss/oxide': '4.3.1',
            tailwindcss: '4.3.1',
        });
        expect(packageLock.packages['node_modules/@tailwindcss/node'].dependencies.tailwindcss).toBe('4.3.1');

        const oxideOptionalDependencies = packageLock.packages['node_modules/@tailwindcss/oxide'].optionalDependencies;
        for (const [packageName, version] of Object.entries(oxideOptionalDependencies)) {
            expect(version).toBe('4.3.1');
            expect(packageLock.packages[`node_modules/${packageName}`]).toMatchObject({ optional: true, version });
        }
    });

    it('approves exactly the packages whose locked nodes run install scripts', () => {
        const lockedInstallScripts = Object.entries(packageLock.packages)
            .filter(([, metadata]) => metadata.hasInstallScript)
            .map(([lockPath, metadata]) => `${lockPath.replace(/^node_modules\//, '')}@${metadata.version}`)
            .sort();

        expect(packageJson.allowScripts).toEqual({
            '@parcel/watcher@2.5.1': true,
            'esbuild@0.28.1': true,
            'fsevents@2.3.3': true,
        });
        expect(Object.keys(packageJson.allowScripts).sort()).toEqual(lockedInstallScripts);
    });

    it('keeps all Tailwind script interfaces and uses the v4 CLI syntax', () => {
        const expected = {
            'build:tailwind:public': 'tailwindcss -i ./tailwind_css/public/style.css -o ./frontend_public/static/css/style.css --minify',
            'build:tailwind:private': 'tailwindcss -i ./tailwind_css/private/style.css -o ./frontend_private/static/private/css/style.css --minify',
            'dev:tailwind:public': 'tailwindcss -i ./tailwind_css/public/style.css -o ./frontend_public/static/css/style.css -w',
            'dev:tailwind:private': 'tailwindcss -i ./tailwind_css/private/style.css -o ./frontend_private/static/private/css/style.css -w',
            'pre-commit:tailwind:public': 'tailwindcss -i ./tailwind_css/public/style.css -o ./frontend_public/static/css/style.css',
            'pre-commit:tailwind:private': 'tailwindcss -i ./tailwind_css/private/style.css -o ./frontend_private/static/private/css/style.css',
        };

        for (const [name, command] of Object.entries(expected)) {
            expect(packageJson.scripts[name]).toBe(command);
            expect(command).not.toContain(' -c ');
        }
    });

    it('freezes entrypoint import, source, layer, and variant order', () => {
        expectInOrder(publicCss, [
            "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;800&display=fallback');",
            "@import 'tailwindcss' source(none);",
            '@config "./tailwind.config.js";',
            "@import '../shared/design-system.css';",
            "@import './additional-styles/utility-patterns.css' layer(components);",
            "@import './additional-styles/theme.css' layer(components);",
            '@source "../../frontend_public/templates/**/*.html";',
            '@source "../../frontend_public/static/js/*.js";',
            '@source "../../frontend_public/templatetags/people_tags.py";',
            '@custom-variant hover (&:hover);',
            '@custom-variant group-hover (.group:hover &);',
            '@layer utilities',
        ]);
        expectInOrder(privateCss, [
            "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=fallback');",
            "@import 'tailwindcss' source(none);",
            '@config "./tailwind.config.js";',
            "@import '../shared/design-system.css';",
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
    });

    it('disables automatic source detection and owns the exact source sets in CSS', () => {
        expect(publicCss).toContain("@import 'tailwindcss' source(none);");
        expect(privateCss).toContain("@import 'tailwindcss' source(none);");
        expect(sourceDirectives(publicCss)).toEqual([
            '../../frontend_public/templates/**/*.html',
            '../../frontend_public/static/js/*.js',
            '../../frontend_public/templatetags/people_tags.py',
        ]);
        expect(sourceDirectives(privateCss)).toEqual([
            '../../frontend_private/templates/**/*.html',
            '../../frontend_public/templates/footer.html',
            '../../frontend_private/static/private/js/*.js',
            '../../frontend_private/static/private/js/map_viewer/**/*.js',
            '../../speleodb/surveys/templatetags/project_types.py',
        ]);
    });

    it('uses durable product names for shared production CSS', () => {
        const productionCss = listFiles('tailwind_css', true, CSS_EXTENSIONS);
        const productionSources = [...new Set([
            ...compilerOwnedSourceFiles(),
            ...productionCss,
        ])].sort();

        expect(fs.existsSync(path.join(ROOT, 'tailwind_css/shared/v3-compat.css'))).toBe(false);
        expect(fs.existsSync(path.join(ROOT, 'tailwind_css/shared/design-system.css'))).toBe(true);

        for (const relativePath of productionSources) {
            expect(read(relativePath), `${relativePath} exposes a migration-version name`)
                .not.toMatch(/(?:^|[^a-z0-9])v3-/im);
        }

        expect(designSystemCss).toContain('@utility flow-y-4');
        expect(designSystemCss).toContain('@utility row-divide-y');
        expect(designSystemCss).toContain('--color-srgb-slate-700-50:');
    });

    it('proves source inclusion, exclusion, and cross-build isolation with the real compiler', () => {
        const { publicOutput, privateOutput } = compileSourceMirror();

        for (const value of [101, 102, 103, 104]) {
            expect(publicOutput, `Public build omitted z-[${value}]`).toContain(`z-index:${value}`);
        }
        for (const value of [191, 201, 202, 203, 204, 291, 292]) {
            expect(publicOutput, `Public build leaked z-[${value}]`).not.toContain(`z-index:${value}`);
        }

        for (const value of [102, 201, 202, 203, 204]) {
            expect(privateOutput, `Private build omitted z-[${value}]`).toContain(`z-index:${value}`);
        }
        for (const value of [101, 103, 104, 191, 291, 292]) {
            expect(privateOutput, `Private build leaked z-[${value}]`).not.toContain(`z-index:${value}`);
        }
    }, 30_000);

    it('loads one legacy config and one copy of each plugin per build', () => {
        expect(publicCss).toContain('@config "./tailwind.config.js";');
        expect(privateCss).toContain('@config "./tailwind.config.js";');

        for (const [css, config] of [[publicCss, publicConfig], [privateCss, privateConfig]]) {
            expect(css).not.toContain('@plugin');
            expect(config.match(/require\('@tailwindcss\/forms'\)/g)).toHaveLength(1);
            expect(config.match(/require\('@tailwindcss\/typography'\)/g)).toHaveLength(1);
            expect(config).toContain("require('@tailwindcss/forms')({ strategy: 'base' })");
            expect(config).not.toMatch(/\bcontent\s*:/);
            expect(config).not.toMatch(/\bdarkMode\s*:/);
        }
    });

    it('freezes every v3 palette value and relevant default token against an independent fixture', () => {
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

        expect(designSystemCss).toContain('border-color: var(--color-gray-200);');
        expect(designSystemCss).toContain('@utility flow-y-4');
        expect(designSystemCss).toContain('@utility row-divide-y');
        expect(designSystemCss).toContain('& > :not([hidden]) ~ :not([hidden])');
        expect(designSystemCss).toContain("input:where([type='checkbox']):checked");
        expect(designSystemCss).toContain('data:image/svg+xml;base64');
    });

    it('inspects all compiler-owned source and runtime candidate contexts for removed v3 forms', () => {
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

        const classContexts = compilerOwnedSourceFiles()
            .flatMap(relativePath => [
                ...read(relativePath).matchAll(/\b(?:class|:class|x-bind:class)\s*=\s*["'`]([^"'`]*)["'`]/g),
            ])
            .map(match => match[1])
            .join('\n');
        expect(classContexts).not.toMatch(/(?:^|\s)(?:![A-Za-z]|[A-Za-z0-9-]+:![A-Za-z])/m);
    });

    it('rejects application coupling to every Tailwind private variable', () => {
        const processedCss = [
            ...listFiles('tailwind_css', true, CSS_EXTENSIONS),
            ...listFiles('frontend_public', true, CSS_EXTENSIONS),
            ...listFiles('frontend_private', true, CSS_EXTENSIONS),
        ].filter(relativePath => ![
            'tailwind_css/shared/design-system.css',
            'frontend_public/static/css/style.css',
            'frontend_private/static/private/css/style.css',
        ].includes(relativePath) && !relativePath.includes('/vendors/'));
        const applicationSources = [...new Set([
            ...compilerOwnedSourceFiles(),
            ...processedCss,
        ])].sort();

        for (const relativePath of applicationSources) {
            expect(read(relativePath), `${relativePath} couples to Tailwind internals`).not.toMatch(/--tw-[a-z0-9-]+/i);
        }
    });

    it('freezes the four production stylesheet compositions', () => {
        const publicBase = read('frontend_public/templates/base.html');
        const privateBase = read('frontend_private/templates/base_private.html');
        const publicMap = read('frontend_public/templates/pages/gis_view_map.html');
        const privateMap = read('frontend_private/templates/pages/map_viewer.html');

        expectInOrder(publicBase, [
            "{% static 'css/vendors/aos.css' %}",
            'https://cdnjs.cloudflare.com/ajax/libs/aos/3.0.0-beta.6/aos.css',
            "{% static 'css/style.css' %}",
            "{% static 'css/custom.css' %}",
            '{% block extra_css %}',
        ]);
        expectInOrder(privateBase, [
            "{% static 'private/css/style.css' %}",
            "{% static 'private/css/custom.css' %}",
            '<style>',
            '{% block extra_css %}',
        ]);
        expectInOrder(publicMap, [
            "{% static 'private/css/style.css' %}",
            "{% static 'private/css/custom.css' %}",
            "{% static 'private/css/shared-modal.css' %}",
            "{% static 'private/css/map_viewer.css' %}",
            'https://api.mapbox.com/mapbox-gl-js/v3.12.0/mapbox-gl.css',
        ]);
        expectInOrder(privateMap, [
            'https://api.mapbox.com/mapbox-gl-js/v3.12.0/mapbox-gl.css',
            "{% static 'private/css/shared-modal.css' %}",
            "{% static 'private/css/map_viewer.css' %}",
        ]);
    });

    it('keeps component line-height literal so responsive text utilities can win', () => {
        const cleanPrivateCss = compileCleanPrivateOutput();
        const buttonSelector = '.btn,.btn-lg,.btn-sm,.btn-xs';
        const formSelector = '.form-input,.form-textarea,.form-multiselect,.form-select';
        const buttonRules = cssRuleBodies(cleanPrivateCss, buttonSelector).join(';');
        const formRules = cssRuleBodies(cleanPrivateCss, formSelector).join(';');
        const responsiveTextRule = cssRuleBodies(cleanPrivateCss, '.md\\:text-base').join(';');

        for (const [selector, rules] of [[buttonSelector, buttonRules], [formSelector, formRules]]) {
            expect(rules, `Clean build omitted ${selector}`).not.toBe('');
            expect(rules, `${selector} lost the v3 line-height`).toContain('line-height:1.25rem');
            expect(rules, `${selector} leaks inherited leading state`).not.toMatch(/--tw-leading\s*:/);
        }

        expect(responsiveTextRule).toContain('font-size:1rem');
        expect(responsiveTextRule).toContain('line-height:var(--tw-leading,1.5)');
        expect(cleanPrivateCss.indexOf('.md\\:text-base{')).toBeGreaterThan(
            Math.max(
                cleanPrivateCss.lastIndexOf(`${buttonSelector}{`),
                cleanPrivateCss.lastIndexOf(`${formSelector}{`),
            ),
        );
    }, 30_000);

    it('compiles the git browser surface without a stale background-owning component', () => {
        expect(gitViewTemplate.match(/bg-linear-to-b\/srgb from-white to-gray-100/g)).toHaveLength(2);
        expect(privateComponents).not.toMatch(/\.git_btn\s*{/);
        expect(privateCustomCss).not.toMatch(/\.git_btn\s*{/);

        const cleanPrivateCss = compileCleanPrivateOutput();
        expect(cleanPrivateCss).toContain('.bg-linear-to-b\\/srgb');
        expect(cleanPrivateCss).toContain('.from-white');
        expect(cleanPrivateCss).toContain('.to-gray-100');
        expect(cleanPrivateCss).toContain('.rounded-full');
        expect(cleanPrivateCss).toContain('.cursor-pointer');
        expect(cleanPrivateCss).not.toMatch(/\.git_btn\s*\{[^}]*\bbackground(?:-image)?\s*:/);
    }, 30_000);
});
