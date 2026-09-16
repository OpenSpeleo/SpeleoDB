import fs from 'node:fs';
import path from 'node:path';

function templateSource(file) {
    return fs.readFileSync(path.join(process.cwd(), file), 'utf8');
}

function templateFragment(file) {
    const fragment = document.createElement('template');
    // These checks exercise static DOM contracts, independent of server context.
    fragment.innerHTML = templateSource(file)
        .replace(/{% comment %}[\s\S]*?{% endcomment %}/g, '')
        .replace(/{%[\s\S]*?%}/g, '')
        .replace(/{{[\s\S]*?}}/g, '');
    return fragment.content;
}

describe('public template HTML contracts', () => {
    afterEach(() => {
        document.body.replaceChildren();
    });

    it('toggles public depth coloring once when clicking its full label or checkbox', () => {
        document.body.append(templateFragment('frontend_public/templates/pages/gis_view_map.html'));
        const label = document.getElementById('color-mode-button');
        const checkbox = document.getElementById('color-mode-toggle');
        const changed = vi.fn();
        checkbox.addEventListener('change', changed);

        expect(label.tagName).toBe('LABEL');
        expect(checkbox.labels).toContain(label);
        expect(checkbox.getAttribute('aria-label')).toBe('Color by depth');
        label.click();
        expect(checkbox.checked).toBe(true);
        expect(changed).toHaveBeenCalledTimes(1);
        checkbox.click();
        expect(checkbox.checked).toBe(false);
        expect(changed).toHaveBeenCalledTimes(2);
    });

    it('keeps both logout actions as standalone submit buttons with a POST form', () => {
        const fragment = templateFragment('frontend_public/templates/base.html');
        const forms = [...fragment.querySelectorAll('form')];
        expect(forms).toHaveLength(2);
        for (const form of forms) {
            expect(form.method).toBe('post');
            expect(form.closest('a, button')).toBeNull();
            const button = form.querySelector('button');
            expect(button.type).toBe('submit');
            expect(button.textContent).toContain('Sign Out');
            expect(button.querySelector('a, button')).toBeNull();
        }
    });

    it('keeps the error recovery action as one navigation link', () => {
        const fragment = templateFragment('frontend_errors/templates/base_error.html');
        const link = fragment.querySelector('.denied__link');
        expect(link.tagName).toBe('A');
        expect(link.hasAttribute('href')).toBe(true);
        expect(link.querySelector('button')).toBeNull();
    });

    it('preserves unfilled SVG feature icons after duplicate class cleanup', () => {
        const fragment = templateFragment('frontend_public/templates/pages/home.html');
        const icons = [...fragment.querySelectorAll('svg.icon-tabler')];
        expect(icons).toHaveLength(4);
        for (const icon of icons) {
            expect(icon.getAttribute('fill')).toBe('none');
            expect(icon.classList.contains('fill-slate-300')).toBe(false);
        }
    });
});
