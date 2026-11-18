import { init } from './donation-campaign.ts';
import { setBrowserUrl, startApiServer } from '../test/api-server.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
const originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal');
const originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close');
beforeAll(async () => { originalUrl = window.location.href; server = await startApiServer(); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });

beforeEach(() => {
    server.reset();
    server.reply({ status: 204 });
    setBrowserUrl(`${server.origin}/private/`);
    document.body.innerHTML = '<input type="hidden" name="csrfmiddlewaretoken" value="campaign-csrf"><h1 id="dashboard-heading" tabindex="-1">Dashboard</h1><button data-campaign-open>About</button><dialog id="donation-campaign"><h2 tabindex="-1">Fundraiser</h2><button data-campaign-dismiss>Remind me in one week</button></dialog><p id="campaign-save-error" hidden><button data-campaign-retry>Retry</button></p>';
    // JSDOM does not implement native dialog presentation.
    HTMLDialogElement.prototype.showModal = function () { this.open = true; };
    HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new Event('close')); };
});
afterEach(() => {
    document.body.innerHTML = '';
    for (const [name, descriptor] of [['showModal', originalShowModal], ['close', originalClose]] as const) {
        if (descriptor) Object.defineProperty(HTMLDialogElement.prototype, name, descriptor);
        else Reflect.deleteProperty(HTMLDialogElement.prototype, name);
    }
});
it('does not automatically reopen a dismissed invitation but allows manual discovery', () => {
    init({ campaignId: 'campaign', shouldInvite: false });
    const dialog = document.querySelector('dialog')!;
    expect(dialog.open).toBe(false);
    document.querySelector<HTMLButtonElement>('[data-campaign-open]')!.click();
    expect(dialog.open).toBe(true);
    expect(document.activeElement).toBe(dialog.querySelector('h2'));
});
it('opens an eligible invitation independently of dashboard statistics', () => {
    init({ campaignId: 'campaign', shouldInvite: true });
    expect(document.querySelector('dialog')!.open).toBe(true);
});
it('does not interrupt an existing dialog', () => {
    document.body.insertAdjacentHTML('beforeend', '<dialog open>Other work</dialog>');
    init({ campaignId: 'campaign', shouldInvite: true });
    expect(document.querySelector('dialog')!.open).toBe(false);
});

it('does not interrupt a user who has already focused a dashboard control', () => {
    document.querySelector<HTMLButtonElement>('[data-campaign-open]')!.focus();
    init({ campaignId: 'campaign', shouldInvite: true });
    expect(document.querySelector('dialog')!.open).toBe(false);
});

for (const action of ['button', 'escape', 'backdrop', 'donate']) {
    it(`persists ${action} dismissal once and restores focus`, async () => {
        document.querySelector('dialog')!.insertAdjacentHTML('beforeend', '<a href="#" data-campaign-donate>Donate</a>');
        init({ campaignId: '7e33c4c2-6419-4a24-b394-f86d3249eaa0', shouldInvite: true });
        const dialog = document.querySelector('dialog')!;
        if (action === 'escape') dialog.dispatchEvent(new Event('cancel', { cancelable: true }));
        else if (action === 'backdrop') dialog.dispatchEvent(new MouseEvent('click', { clientX: -1 }));
        else document.querySelector<HTMLElement>(action === 'donate' ? '[data-campaign-donate]' : '[data-campaign-dismiss]')!.click();
        expect(dialog.open).toBe(false);
        expect(document.activeElement?.id).toBe('dashboard-heading');
        await vi.waitFor(() => expect(server.requests).toHaveLength(1));
        expect(server.requests[0]).toMatchObject({ method: 'POST', path: '/api/v2/user/donation-campaigns/7e33c4c2-6419-4a24-b394-f86d3249eaa0/dismiss/', headers: { 'x-csrftoken': 'campaign-csrf' } });
    });
}
it('keeps the dialog closed and exposes an explicit retry control on save failure', async () => {
    server.reply({ status: 500, json: { detail: 'Unavailable' } });
    init({ campaignId: '7e33c4c2-6419-4a24-b394-f86d3249eaa0', shouldInvite: true });
    document.querySelector<HTMLButtonElement>('[data-campaign-dismiss]')!.click();
    const notice = document.querySelector<HTMLElement>('#campaign-save-error')!;
    await vi.waitFor(() => expect(notice.hidden).toBe(false));
    expect(document.querySelector('dialog')!.open).toBe(false);
    expect(notice.querySelector('[data-campaign-retry]')).not.toBeNull();
    expect(server.requests).toHaveLength(1);
});

it('records a new reminder when an already-dismissed campaign is reopened and closed', async () => {
    init({ campaignId: '7e33c4c2-6419-4a24-b394-f86d3249eaa0', shouldInvite: false });
    document.querySelector<HTMLButtonElement>('[data-campaign-open]')!.click();
    document.querySelector<HTMLButtonElement>('[data-campaign-dismiss]')!.click();
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
});

it('switches to the story and back without recording a dismissal', () => {
    const dialog = document.querySelector('dialog')!;
    dialog.innerHTML = '<section data-campaign-overview><h2 id="campaign-heading" tabindex="-1">Fundraiser</h2><button data-campaign-story-open>Read the campaign story</button></section><section data-campaign-story hidden><button data-campaign-story-back>Back</button><h2 id="campaign-story-heading" tabindex="-1">Campaign story</h2><p>Full story</p></section>';
    dialog.classList.add('donation-dialog');
    init({ campaignId: 'campaign', shouldInvite: true });
    const link = dialog.querySelector<HTMLButtonElement>('[data-campaign-story-open]')!;
    link.click();
    expect(dialog.querySelector<HTMLElement>('[data-campaign-overview]')!.hidden).toBe(true);
    expect(dialog.querySelector<HTMLElement>('[data-campaign-story]')!.hidden).toBe(false);
    expect(document.activeElement?.id).toBe('campaign-story-heading');
    expect(dialog.getAttribute('aria-labelledby')).toBe('campaign-story-heading');
    dialog.querySelector<HTMLButtonElement>('[data-campaign-story-back]')!.click();
    expect(dialog.querySelector<HTMLElement>('[data-campaign-overview]')!.hidden).toBe(false);
    expect(dialog.querySelector<HTMLElement>('[data-campaign-story]')!.hidden).toBe(true);
    expect(document.activeElement).toBe(link);
    expect(dialog.open).toBe(true);
    expect(server.requests).toHaveLength(0);
});

it('renews the reminder when donating from the card before the invitation is due', async () => {
    document.body.insertAdjacentHTML('beforeend', '<a href="#" data-campaign-donate>Donate from card</a>');
    init({ campaignId: '7e33c4c2-6419-4a24-b394-f86d3249eaa0', shouldInvite: false });
    document.querySelector<HTMLElement>('[data-campaign-donate]')!.click();
    await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    expect(document.querySelector('dialog')!.open).toBe(false);
    expect(server.requests[0]).toMatchObject({ method: 'POST', headers: { 'x-csrftoken': 'campaign-csrf' } });
});
