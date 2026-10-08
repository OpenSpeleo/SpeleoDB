// @vitest-environment node

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { JSDOM } from 'jsdom';
import type { DOMWindow } from 'jsdom';
import type { AlpineRuntime, AlpineBindings } from '../../ts-types/browser/alpine.d.ts';
type AlpineWindow = DOMWindow & { Alpine: AlpineRuntime };


import { registerAlpineBindings } from '../runtime/alpine.ts';
import { privateBindings } from '../bindings/private.ts';
import { publicBindings } from '../bindings/public.ts';
import { revisionBindings } from '../bindings/revision.ts';
const bindings: AlpineBindings = { ...privateBindings, ...publicBindings, ...revisionBindings };
function bound(root: ParentNode, directive: string) { return [...root.querySelectorAll<HTMLElement>('[data-speleodb-bind]')].find(element => directive in bindings[element.dataset.speleodbBind!]!)!; }

const ROOT = process.cwd();
const VENDOR = readFileSync(path.join(ROOT, 'frontend_public/static/ts/vendors/alpinejs.min.js'), 'utf8');
const openWindows: DOMWindow[] = [];

function template(filename: string, preferences: Record<string, boolean> = {}) {
    return readFileSync(path.join(ROOT, filename), 'utf8')
        .replace(/{% if user\.(email_on_\w+) %}true{% else %}false{% endif %}/g,
            (_match: string, name: string) => String(preferences[name] ?? false))
        .replace(/{%[\s\S]*?%}/g, '')
        .replace(/{{[\s\S]*?}}/g, '');
}

async function startVendor(html: string) {
    const dom = new JSDOM(html, {
        runScripts: 'outside-only',
        pretendToBeVisual: true,
        url: 'http://localhost/',
    });
    const window = dom.window as AlpineWindow;
    openWindows.push(window);
    const events: string[] = [];
    window.document.addEventListener('alpine:init', () => events.push('init'));
    const initialized = new Promise<void>(resolve => {
        window.document.addEventListener('alpine:initialized', () => {
            events.push('initialized');
            resolve();
        }, { once: true });
    });
    window.eval(VENDOR);
    // The distributed vendor queues startup; application code must not invoke
    // start() a second time when moving the existing scopes into typed modules.
    expect(events).toEqual([]);
    await initialized;
    registerAlpineBindings(bindings, window as unknown as Window);
    await window.Alpine.nextTick();
    expect(events).toEqual(['init', 'initialized']);
    return window;
}

function makeVisible(element: HTMLElement) {
    // JSDOM has no layout. Alpine's outside-click guard requires a nonzero box;
    // provide only that browser measurement, retaining the real event handlers.
    Object.defineProperties(element, {
        offsetWidth: { configurable: true, value: 100 },
        offsetHeight: { configurable: true, value: 100 },
    });
}

afterEach(() => {
    for (const window of openWindows.splice(0)) window.close();
});

describe('vendored Alpine template behavior after typed binding extraction', () => {
    it('auto-starts the private sidebar, preserves stopped clicks, and closes on outside click and Escape', async () => {
        const window = await startVendor(template('frontend_private/templates/base_private.html'));
        const { document } = window;
        const sidebar = document.getElementById('sidebar')!;
        const [close, open] = document.querySelectorAll<HTMLElement>('button[aria-controls="sidebar"]');
        makeVisible(sidebar);
        expect(sidebar.hasAttribute('x-cloak')).toBe(false);
        expect(sidebar.classList.contains('-translate-x-full')).toBe(true);
        expect(open!.getAttribute('aria-expanded')).toBe('false');
        const bubbled = vi.fn();
        document.addEventListener('click', bubbled);

        open!.click();
        await window.Alpine.nextTick();
        expect(bubbled).not.toHaveBeenCalled();
        expect(open!.getAttribute('aria-expanded')).toBe('true');
        expect(close!.getAttribute('aria-expanded')).toBe('true');
        expect(sidebar.classList.contains('translate-x-0')).toBe(true);

        document.body.click();
        await window.Alpine.nextTick();
        expect(open!.getAttribute('aria-expanded')).toBe('false');
        open!.click();
        await window.Alpine.nextTick();
        window.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        await window.Alpine.nextTick();
        expect(sidebar.classList.contains('-translate-x-full')).toBe(true);
    });

    it.each([true, false])('keeps preference scopes independent and serializable with initial application updates=%s', async checked => {
        const window = await startVendor(template('frontend_private/templates/pages/user/preferences.html', {
            email_on_speleodb_updates: checked,
            email_on_projects_updates: !checked,
        }));
        const { document } = window;
        const app = document.getElementById('email_on_speleodb_updates') as HTMLInputElement;
        const projects = document.getElementById('email_on_projects_updates') as HTMLInputElement;
        const label = (input: HTMLInputElement) => bound(input.closest('[data-speleodb-scope]')!, 'x-text').textContent;
        expect(app.checked).toBe(checked);
        expect(projects.checked).toBe(!checked);
        expect(label(app)).toBe(checked ? 'On' : 'Off');
        expect(label(projects)).toBe(checked ? 'Off' : 'On');

        app.click();
        await window.Alpine.nextTick();
        expect(app.checked).toBe(!checked);
        expect(projects.checked).toBe(!checked);
        expect(label(app)).toBe(checked ? 'Off' : 'On');
        const form = new window.FormData(document.getElementById('preference_form') as HTMLFormElement);
        expect(form.has(app.name)).toBe(!checked);
        expect(form.has(projects.name)).toBe(!checked);
    });

    it('retains the private user menu prevent, outside, Escape, and transition declarations', async () => {
        const window = await startVendor(template('frontend_private/templates/base_private.html'));
        const button = window.document.querySelector<HTMLElement>('button[aria-haspopup="true"]')!;
        const panel = bound(button.parentElement!, 'x-show');
        makeVisible(panel);
        expect(panel.style.display).toBe('none');
        expect(panel.getAttribute('x-transition:enter')).toContain('duration-200');
        const click = new window.MouseEvent('click', { bubbles: true, cancelable: true });
        button.dispatchEvent(click);
        await window.Alpine.nextTick();
        expect(click.defaultPrevented).toBe(true);
        expect(button.getAttribute('aria-expanded')).toBe('true');
        await vi.waitFor(() => expect(panel.style.display).not.toBe('none'));
        window.document.body.click();
        await vi.waitFor(() => expect(panel.style.display).toBe('none'));
        expect(button.getAttribute('aria-expanded')).toBe('false');
        button.click();
        await window.Alpine.nextTick();
        window.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }));
        await vi.waitFor(() => expect(panel.style.display).toBe('none'));
        expect(button.getAttribute('aria-expanded')).toBe('false');
    });

    it('initializes inserted revision menu clones asynchronously with independent state and focus behavior', async () => {
        const window = await startVendor('<body></body>');
        const source = new window.DOMParser().parseFromString(
            template('frontend_private/templates/pages/project/revision_history.html'), 'text/html',
        ).querySelector('#commit-template [data-speleodb-scope]')!;
        const first = source.cloneNode(true) as HTMLElement;
        const second = source.cloneNode(true) as HTMLElement;
        window.document.body.append(first, second);
        const firstButton = first.querySelector('button')!;
        const secondButton = second.querySelector('button')!;
        expect(firstButton.hasAttribute('aria-expanded')).toBe(false);
        expect(first.querySelector('[x-cloak]')).not.toBeNull()!;
        await window.Alpine.nextTick();
        expect(firstButton.getAttribute('aria-expanded')).toBe('false');
        expect(secondButton.getAttribute('aria-expanded')).toBe('false');
        expect(first.querySelector('[x-cloak]')).toBeNull()!;

        firstButton.click();
        await window.Alpine.nextTick();
        expect(firstButton.getAttribute('aria-expanded')).toBe('true');
        expect(secondButton.getAttribute('aria-expanded')).toBe('false');
        const link = second.querySelector('a')!;
        link.dispatchEvent(new window.FocusEvent('focus'));
        await window.Alpine.nextTick();
        expect(secondButton.getAttribute('aria-expanded')).toBe('true');
        link.dispatchEvent(new window.FocusEvent('focusout'));
        await window.Alpine.nextTick();
        expect(secondButton.getAttribute('aria-expanded')).toBe('false');
        expect(firstButton.getAttribute('aria-expanded')).toBe('true');
    });
});

it.each(['cylinder_fleet', 'experiment', 'gis_view', 'project', 'sensor_fleet', 'surface_network', 'team', 'tools', 'user', 'shared/entity_settings'])('keeps the %s menu own scope, outside behavior and absent ARIA', async name => {
    const window = await startVendor(template(`frontend_private/templates/pages/${name}/base.html`));
    const scope = window.document.querySelector<HTMLElement>('[data-speleodb-scope]')!;
    const button = scope.querySelector('button')!;
    const panel = bound(scope, 'x-show');
    makeVisible(panel);
    expect(button.hasAttribute('aria-expanded')).toBe(false);
    expect(panel.style.display).toBe('none');
    button.click();
    await window.Alpine.nextTick();
    expect(button.classList.contains('open')).toBe(true);
    window.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }));
    await window.Alpine.nextTick();
    expect(button.classList.contains('open')).toBe(true);
    panel.querySelector('a')!.click();
    await window.Alpine.nextTick();
    expect(button.classList.contains('open')).toBe(false);
    await vi.waitFor(() => expect(panel.style.display).toBe('none'));
    const click = new window.MouseEvent('click', { bubbles: true, cancelable: true });
    button.dispatchEvent(click);
    await window.Alpine.nextTick();
    expect(click.defaultPrevented).toBe(false);
    expect(button.classList.contains('open')).toBe(true);
    await vi.waitFor(() => expect(panel.style.display).not.toBe('none'));
    window.document.body.click();
    await window.Alpine.nextTick();
    expect(button.classList.contains('open')).toBe(false);
});
it('preserves public mobile measurements and welcome Escape behavior', async () => {
    const window = await startVendor(template('frontend_public/templates/base.html') + template('frontend_public/templates/snippets/welcome_modal.html'));
    const nav = window.document.getElementById('mobile-nav')!;
    Object.defineProperty(nav, 'scrollHeight', { value: 230 });
    const button = window.document.querySelector<HTMLElement>('button[aria-controls="mobile-nav"]')!;
    button.click();
    await window.Alpine.nextTick();
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(nav.style.maxHeight).toBe('230px');
    const welcome = window.document.querySelector<HTMLElement>('[data-speleodb-bind="public-snippets-welcome_modal-1"]')!;
    expect(welcome.style.display).not.toBe('none');
    window.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }));
    await window.Alpine.nextTick();
    await vi.waitFor(() => expect(welcome.style.display).toBe('none'));
    expect(button.getAttribute('aria-expanded')).toBe('false');
});

it('waits for a missing vendor without blocking, then initializes once after its own auto-start', async () => {
    const dom = new JSDOM(template('frontend_private/templates/base_private.html'), { runScripts: 'outside-only', pretendToBeVisual: true });
    const window = dom.window as AlpineWindow;
    openWindows.push(window);
    expect(() => registerAlpineBindings(privateBindings, window as unknown as Window)).not.toThrow();
    registerAlpineBindings(privateBindings, window as unknown as Window);
    const events: string[] = [];
    window.document.addEventListener('alpine:initialized', () => events.push('initialized'));
    window.eval(VENDOR);
    await new Promise<void>(resolve => window.document.addEventListener('alpine:initialized', () => resolve(), { once: true }));
    await window.Alpine.nextTick();
    const open = window.document.querySelectorAll<HTMLButtonElement>('button[aria-controls="sidebar"]')[1]!;
    registerAlpineBindings(privateBindings, window as unknown as Window);
    await window.Alpine.nextTick();
    open.click();
    await window.Alpine.nextTick();
    expect(open.getAttribute('aria-expanded')).toBe('true');
    expect(events).toEqual(['initialized']);
});

it('reinitializes a detached revision scope through the vendor cleanup lifecycle', async () => {
    const window = await startVendor(template('frontend_private/templates/pages/project/revision_history.html'));
    const scope = window.document.querySelector<HTMLElement>('#commit-template [data-speleodb-scope]')!;
    const button = scope.querySelector('button')!;
    button.click();
    await window.Alpine.nextTick();
    expect(button.getAttribute('aria-expanded')).toBe('true');
    scope.remove();
    await window.Alpine.nextTick();
    window.document.body.append(scope);
    await window.Alpine.nextTick();
    expect(button.getAttribute('aria-expanded')).toBe('false');
    button.click();
    await window.Alpine.nextTick();
    expect(button.getAttribute('aria-expanded')).toBe('true');
});

it('retains the generated mobile revision menu separate scope without adding desktop ARIA or Escape', async () => {
    const window = await startVendor('<body></body>');
    const source = readFileSync(path.join(ROOT, 'frontend_common/controllers/revision-history.ts'), 'utf8');
    const markup = source.match(/var \$downloadBtn = \$\('([^\n]+)'\);/)![1]!;
    const host = window.document.createElement('div');
    host.innerHTML = markup;
    window.document.body.append(host);
    const button = host.querySelector('button')!;
    const panel = bound(host, 'x-show');
    expect(panel.hasAttribute('x-cloak')).toBe(true);
    await window.Alpine.nextTick();
    expect(panel.style.display).toBe('none');
    expect(button.hasAttribute('aria-expanded')).toBe(false);
    button.click();
    await window.Alpine.nextTick();
    await vi.waitFor(() => expect(panel.style.display).not.toBe('none'));
    window.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }));
    await window.Alpine.nextTick();
    expect(panel.style.display).not.toBe('none');
});

it('waits for parent registration and keeps separate route binding ownership', async () => {
    const privateSource = template('frontend_private/templates/base_private.html');
    const revisionSource = template('frontend_private/templates/pages/project/revision_history.html');
    const dom = new JSDOM(privateSource.replace('</body>', `${revisionSource}</body>`), { runScripts: 'outside-only', pretendToBeVisual: true });
    const window = dom.window as AlpineWindow;
    openWindows.push(window);
    window.eval(VENDOR);
    await new Promise<void>(resolve => window.document.addEventListener('alpine:initialized', () => resolve(), { once: true }));
    registerAlpineBindings(revisionBindings, window as unknown as Window);
    await window.Alpine.nextTick();
    const revision = window.document.querySelector<HTMLButtonElement>('#commit-template button')!;
    expect(revision.hasAttribute('aria-expanded')).toBe(false);
    registerAlpineBindings(privateBindings, window as unknown as Window);
    await window.Alpine.nextTick();
    expect(revision.getAttribute('aria-expanded')).toBe('false');
    revision.click();
    await window.Alpine.nextTick();
    expect(revision.getAttribute('aria-expanded')).toBe('true');
    expect(window.document.querySelectorAll('button[aria-controls="sidebar"]')[1]!.getAttribute('aria-expanded')).toBe('false');
});

it('keeps generated revision menus independent without adding Escape, ARIA or focus behavior', async () => {
    const menu = `<div data-speleodb-scope data-speleodb-bind="revision-controllers-revision-history-1">
        <button data-speleodb-bind="revision-controllers-revision-history-2">Open</button>
        <div data-speleodb-bind="revision-controllers-revision-history-3"><a href="#">Revision</a></div>
    </div>`;
    const window = await startVendor(`<body>${menu}${menu}</body>`);
    const scopes = window.document.querySelectorAll<HTMLElement>('[data-speleodb-scope]');
    const firstButton = scopes[0]!.querySelector('button')!;
    const firstPanel = bound(scopes[0]!, 'x-show');
    const secondPanel = bound(scopes[1]!, 'x-show');
    makeVisible(firstPanel);
    makeVisible(secondPanel);
    firstButton.click();
    await window.Alpine.nextTick();
    await vi.waitFor(() => expect(firstPanel.style.display).not.toBe('none'));
    expect(secondPanel.style.display).toBe('none');
    expect(firstButton.hasAttribute('aria-expanded')).toBe(false);
    window.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }));
    secondPanel.querySelector('a')!.dispatchEvent(new window.FocusEvent('focus'));
    await window.Alpine.nextTick();
    expect(firstPanel.style.display).not.toBe('none');
    expect(secondPanel.style.display).toBe('none');
    window.document.body.click();
    await window.Alpine.nextTick();
    await vi.waitFor(() => expect(firstPanel.style.display).toBe('none'));
});
