/**
 * Tests for the color picker UI (color-picker.js).
 *
 * Loads the real initColorPicker and _hexBodyRe from the source via
 * a lightweight jQuery shim over jsdom so every test exercises
 * production code rather than local copies.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

/* ── Load real source ──────────────────────────────────────────── */

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC_PATH = resolve(__dirname, '..', 'color-picker.js');
const SRC_TEXT = readFileSync(SRC_PATH, 'utf-8');

/**
 * Minimal jQuery shim backed by jsdom's querySelectorAll.
 * Supports only the subset used by color-picker.js.
 */
function jQueryShim(selectorOrEl) {
    const elements = (selectorOrEl instanceof Element)
        ? [selectorOrEl]
        : Array.from(document.querySelectorAll(selectorOrEl));

    const wrapper = {
        val(v) {
            if (v === undefined) return elements[0]?.value ?? '';
            elements.forEach(el => { el.value = v; });
            return wrapper;
        },
        css(prop, value) {
            elements.forEach(el => el.style.setProperty(prop, value));
            return wrapper;
        },
        click(handler) {
            if (typeof handler === 'function') {
                elements.forEach(el => el.addEventListener('click', handler));
            } else {
                elements.forEach(el => el.click());
            }
            return wrapper;
        },
        on(event, handler) {
            elements.forEach(el => el.addEventListener(event, handler));
            return wrapper;
        },
        addClass(classes) {
            classes.split(/\s+/).filter(Boolean).forEach(c =>
                elements.forEach(el => el.classList.add(c))
            );
            return wrapper;
        },
        removeClass(classes) {
            classes.split(/\s+/).filter(Boolean).forEach(c =>
                elements.forEach(el => el.classList.remove(c))
            );
            return wrapper;
        },
        data(key) { return elements[0]?.dataset[key]; },
    };
    return wrapper;
}

const _loader = new Function('$', SRC_TEXT + '\nreturn { _hexBodyRe, initColorPicker };');
const { _hexBodyRe, initColorPicker } = _loader(jQueryShim);

/* ── Selectors matching the test DOM ──────────────────────────── */

const OPTS = {
    preview:      '#color-preview',
    hiddenInput:  '#color-value',
    nativePicker: '#color-picker',
    pickerBtn:    '#color-picker-btn',
    hexInput:     '#color-hex-input',
    presets:      '.color-preset',
};

/* ── DOM scaffolding ──────────────────────────────────────────── */

function createWritableDOM(initialColor = '#e41a1c') {
    const hex = initialColor.replace('#', '');
    document.body.innerHTML = `
        <form id="test-form">
            <fieldset>
                <div class="color-picker-group">
                    <div id="color-preview" style="background-color: ${initialColor}"></div>
                    <button type="button" id="color-picker-btn">Pick</button>
                    <input type="color" id="color-picker" value="${initialColor}" class="sr-only">
                    <input type="hidden" name="color" id="color-value" value="${initialColor}">
                    <input type="text" id="color-hex-input" value="${hex}" maxlength="6">
                    <button type="button" class="color-preset" data-color="#377eb8"></button>
                    <button type="button" class="color-preset" data-color="#4daf4a"></button>
                </div>
                <button id="btn_submit">Save</button>
            </fieldset>
        </form>
    `;
}

function createDisabledDOM(initialColor = '#e41a1c') {
    const hex = initialColor.replace('#', '');
    document.body.innerHTML = `
        <form id="test-form">
            <fieldset disabled>
                <div class="color-picker-group color-picker-disabled">
                    <div id="color-preview" style="background-color: ${initialColor}"></div>
                    <input type="color" id="color-picker" value="${initialColor}" class="sr-only">
                    <input type="hidden" name="color" id="color-value" value="${initialColor}">
                    <input type="text" id="color-hex-input" value="${hex}" maxlength="6" disabled>
                </div>
                <button id="btn_submit" disabled>Save</button>
            </fieldset>
        </form>
    `;
}

/* ── Tests ─────────────────────────────────────────────────────── */

describe('Color Picker UI', () => {
    afterEach(() => {
        document.body.innerHTML = '';
    });

    // ── Writable mode DOM structure ─────────────────────────────────

    describe('writable mode structure', () => {
        beforeEach(() => createWritableDOM('#e41a1c'));

        it('renders color preview with initial color', () => {
            const preview = document.getElementById('color-preview');
            expect(preview).not.toBeNull();
            expect(preview.style.backgroundColor).toBe('rgb(228, 26, 28)');
        });

        it('renders color picker button', () => {
            expect(document.getElementById('color-picker-btn')).not.toBeNull();
        });

        it('renders preset buttons', () => {
            expect(document.querySelectorAll('.color-preset').length).toBe(2);
        });

        it('hidden color input has full hex value with #', () => {
            expect(document.getElementById('color-value').value).toBe('#e41a1c');
        });

        it('hex text input shows value without #', () => {
            expect(document.getElementById('color-hex-input').value).toBe('e41a1c');
        });

        it('hex input is not disabled', () => {
            expect(document.getElementById('color-hex-input').disabled).toBe(false);
        });

        it('save button is not disabled', () => {
            expect(document.getElementById('btn_submit').disabled).toBe(false);
        });

        it('color group does not have disabled class', () => {
            expect(document.querySelector('.color-picker-disabled')).toBeNull();
        });
    });

    // ── Read-only / disabled mode DOM structure ─────────────────────

    describe('disabled mode structure', () => {
        beforeEach(() => createDisabledDOM('#e41a1c'));

        it('does not render color picker button', () => {
            expect(document.getElementById('color-picker-btn')).toBeNull();
        });

        it('does not render color presets', () => {
            expect(document.querySelectorAll('.color-preset').length).toBe(0);
        });

        it('hex input is disabled', () => {
            expect(document.getElementById('color-hex-input').disabled).toBe(true);
        });

        it('save button is disabled', () => {
            expect(document.getElementById('btn_submit').disabled).toBe(true);
        });

        it('color group has disabled class', () => {
            expect(document.querySelector('.color-picker-disabled')).not.toBeNull();
        });

        it('still shows color preview', () => {
            const preview = document.getElementById('color-preview');
            expect(preview).not.toBeNull();
            expect(preview.style.backgroundColor).toBe('rgb(228, 26, 28)');
        });

        it('still shows hex value for reference', () => {
            expect(document.getElementById('color-hex-input').value).toBe('e41a1c');
        });

        it('fieldset is disabled', () => {
            expect(document.querySelector('fieldset').disabled).toBe(true);
        });
    });

    // ── _hexBodyRe (from source) ────────────────────────────────────

    describe('_hexBodyRe (from source)', () => {
        it('accepts valid 6-char hex strings', () => {
            expect(_hexBodyRe.test('e41a1c')).toBe(true);
            expect(_hexBodyRe.test('ABCDEF')).toBe(true);
            expect(_hexBodyRe.test('000000')).toBe(true);
            expect(_hexBodyRe.test('ffffff')).toBe(true);
        });

        it('rejects strings shorter than 6 chars', () => {
            expect(_hexBodyRe.test('abc')).toBe(false);
            expect(_hexBodyRe.test('')).toBe(false);
        });

        it('rejects strings longer than 6 chars', () => {
            expect(_hexBodyRe.test('abcdef0')).toBe(false);
        });

        it('rejects non-hex characters', () => {
            expect(_hexBodyRe.test('ghijkl')).toBe(false);
            expect(_hexBodyRe.test('zzzzzz')).toBe(false);
        });

        it('rejects with # prefix (body only)', () => {
            expect(_hexBodyRe.test('#e41a1c')).toBe(false);
        });
    });

    // ── initColorPicker integration ─────────────────────────────────

    describe('initColorPicker integration', () => {
        let setColor;

        beforeEach(() => {
            createWritableDOM('#e41a1c');
            setColor = initColorPicker(OPTS);
        });

        it('returns a setColor function', () => {
            expect(typeof setColor).toBe('function');
        });

        // ── setColor direct calls ───────────────────────────────

        describe('setColor', () => {
            it('updates hidden input', () => {
                setColor('#377eb8');
                expect(document.getElementById('color-value').value).toBe('#377eb8');
            });

            it('updates native color picker', () => {
                setColor('#377eb8');
                expect(document.getElementById('color-picker').value).toBe('#377eb8');
            });

            it('updates preview background', () => {
                setColor('#377eb8');
                const bg = document.getElementById('color-preview')
                    .style.getPropertyValue('background-color');
                expect(bg).toBe('rgb(55, 126, 184)');
            });

            it('updates hex input without # prefix', () => {
                setColor('#377eb8');
                expect(document.getElementById('color-hex-input').value).toBe('377eb8');
            });

            it('lowercases the hex value', () => {
                setColor('#AABBCC');
                expect(document.getElementById('color-value').value).toBe('#aabbcc');
                expect(document.getElementById('color-hex-input').value).toBe('aabbcc');
            });

            it('highlights matching preset with ring classes', () => {
                setColor('#377eb8');
                const preset = document.querySelector('.color-preset[data-color="#377eb8"]');
                expect(preset.classList.contains('ring-2')).toBe(true);
                expect(preset.classList.contains('ring-white')).toBe(true);
                expect(preset.classList.contains('ring-offset-2')).toBe(true);
            });

            it('removes ring from previously selected preset', () => {
                setColor('#377eb8');
                setColor('#4daf4a');
                const old = document.querySelector('.color-preset[data-color="#377eb8"]');
                expect(old.classList.contains('ring-2')).toBe(false);
            });
        });

        // ── Preset click wiring ─────────────────────────────────

        describe('preset click', () => {
            it('applies preset color to all fields', () => {
                document.querySelector('.color-preset[data-color="#377eb8"]').click();
                expect(document.getElementById('color-value').value).toBe('#377eb8');
                expect(document.getElementById('color-hex-input').value).toBe('377eb8');
            });

            it('preset data-color values are valid hex colors', () => {
                document.querySelectorAll('.color-preset').forEach(preset => {
                    expect(preset.dataset.color).toMatch(/^#[0-9a-fA-F]{6}$/);
                });
            });
        });

        // ── Picker button wiring ────────────────────────────────

        describe('picker button', () => {
            it('delegates click to native color picker', () => {
                const picker = document.getElementById('color-picker');
                const spy = vi.fn();
                picker.addEventListener('click', spy);

                document.getElementById('color-picker-btn').click();
                expect(spy).toHaveBeenCalled();
            });
        });

        // ── Native picker input wiring ──────────────────────────

        describe('native picker input', () => {
            it('applies chosen color when picker value changes', () => {
                const picker = document.getElementById('color-picker');
                picker.value = '#4daf4a';
                picker.dispatchEvent(new Event('input'));
                expect(document.getElementById('color-value').value).toBe('#4daf4a');
                expect(document.getElementById('color-hex-input').value).toBe('4daf4a');
            });
        });

        // ── Hex text input wiring ───────────────────────────────

        describe('hex text input', () => {
            function typeHex(value) {
                const el = document.getElementById('color-hex-input');
                el.value = value;
                el.dispatchEvent(new Event('input'));
                return el;
            }

            it('sanitizes non-hex characters', () => {
                const el = typeHex('zz11gg');
                expect(el.value).toBe('11');
            });

            it('truncates to 6 characters', () => {
                const el = typeHex('aabbccdd');
                expect(el.value).toBe('aabbcc');
            });

            it('applies color when 6 valid hex chars are entered', () => {
                typeHex('377eb8');
                expect(document.getElementById('color-value').value).toBe('#377eb8');
            });

            it('adds error class for incomplete hex', () => {
                const el = typeHex('abc');
                expect(el.classList.contains('border-rose-500')).toBe(true);
            });

            it('removes error class once hex becomes valid', () => {
                const el = typeHex('ab');
                expect(el.classList.contains('border-rose-500')).toBe(true);

                el.value = 'aabbcc';
                el.dispatchEvent(new Event('input'));
                expect(el.classList.contains('border-rose-500')).toBe(false);
                expect(el.classList.contains('border-slate-600')).toBe(true);
            });

            it('shows error state for empty input', () => {
                const el = typeHex('');
                expect(el.classList.contains('border-rose-500')).toBe(true);
            });

            it('strips all invalid chars leaving empty string', () => {
                const el = typeHex('xyz!@#');
                expect(el.value).toBe('');
            });

            it('is case-preserving during sanitization', () => {
                typeHex('ABCdef');
                expect(document.getElementById('color-value').value).toBe('#abcdef');
            });
        });
    });
});
