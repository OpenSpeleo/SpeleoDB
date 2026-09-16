import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { attachFleetEntityCrud } from '../../frontend_private/static/private/js/forms/fleet_entity_crud.js';
import { FormModals } from '../../frontend_private/static/private/js/forms/modals.js';
import { init as initCopyToken } from '../controllers/copy-token.js';

const root = process.cwd();
const jquery = readFileSync(resolve(root, 'frontend_public/static/js/vendors/jquery-3.7.1.js'), 'utf8');
const shellStyles = readFileSync(resolve(root, 'frontend_private/static/private/css/custom.css'), 'utf8');

function templateElement(page, selector) {
    const template = readFileSync(resolve(root, 'frontend_private/templates/pages', page), 'utf8');
    // Resolve inert Django block delimiters for the base confirmation snippet.
    const parsed = new DOMParser().parseFromString(template.replace(/{%.*?%}/gs, ''), 'text/html');
    return parsed.querySelector(selector).cloneNode(true);
}

beforeAll(() => {
    (0, eval)(jquery);
});

beforeEach(() => {
    const style = document.createElement('style');
    style.textContent = shellStyles;
    document.head.append(style);
});

afterEach(() => {
    $(document).off();
    $('body').off();
    document.head.innerHTML = '';
    document.body.innerHTML = '';
});

describe('fleet template modal visibility', () => {
    it.each([
        ['cylinder_fleet/details.html', 'cylinder'],
        ['cylinder_fleet/watchlist.html', 'cylinder'],
        ['sensor_fleet/details.html', 'sensor'],
    ])('%s can open, close, and reopen its CSS-hidden modal', (page, kind) => {
        const modal = templateElement(page, `#${kind}_modal`);
        document.body.append(modal);
        const opener = document.createElement('button');
        opener.id = 'open-modal';
        document.body.append(opener);
        attachFleetEntityCrud({
            modalSelector: `#${kind}_modal`,
            saveButtonSelector: `#${kind}_modal_save`,
            cancelSelectors: `#${kind}_modal_close_x`,
            addButtonSelector: '#open-modal',
            listEndpoint: '/unused/',
            detailEndpoint: id => `/unused/${id}/`,
            resetForCreate: () => {},
            collectPayload: () => null,
        });
        expect(getComputedStyle(modal).display).toBe('none');
        opener.click();
        expect(getComputedStyle(modal).display).toBe('flex');
        document.getElementById(`${kind}_modal_close_x`).click();
        expect(getComputedStyle(modal).display).toBe('none');
        opener.click();
        expect(getComputedStyle(modal).display).toBe('flex');
    });
});

describe('GIS token confirmation visibility', () => {
    it.each(['experiment', 'surface_network'])('%s keeps confirmation hidden until refresh', async kind => {
        const page = `${kind}/gis_integration.html`;
        const modal = templateElement(page, '#refresh-token-modal');
        const form = templateElement(page, '#refresh-token-form');
        document.body.append(form, modal);
        await initCopyToken({
            tokenModal: {
                form: '#refresh-token-form',
                modal: '#refresh-token-modal',
                cancel: '#refresh-token-cancel',
                confirm: '#refresh-token-confirm',
                namedSubmit: true,
            },
        });
        expect(getComputedStyle(modal).display).toBe('none');
        const submit = new Event('submit', { bubbles: true, cancelable: true });
        form.dispatchEvent(submit);
        expect(submit.defaultPrevented).toBe(true);
        expect(getComputedStyle(modal).display).toBe('flex');
        document.getElementById('refresh-token-cancel').click();
        expect(getComputedStyle(modal).display).toBe('none');
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        expect(getComputedStyle(modal).display).toBe('flex');
    });
});


describe('shared feedback modal snippets', () => {
    it.each([
        ['modal_success.html', 'modal_success', 'showSuccess'],
        ['modal_error.html', 'modal_error', 'showError'],
        ['modal_base_confirmation.html', 'modal_confirmation', 'showConfirmation'],
    ])('%s remains hidden until the shared controller opens it', (file, id, show) => {
        const modal = templateElement(`../snippets/${file}`, `#${id}`);
        document.body.append(modal);
        FormModals.bindAutoDismiss();
        expect(getComputedStyle(modal).display).toBe('none');
        FormModals[show]('Test message');
        expect(getComputedStyle(modal).display).toBe('flex');
        modal.querySelector('button').click();
        expect(getComputedStyle(modal).display).toBe('none');
        FormModals[show]('Another message');
        expect(getComputedStyle(modal).display).toBe('flex');
    });
});
