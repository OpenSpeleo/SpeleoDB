import type { MockInstance } from 'vitest';

import { initializeController } from '../app.ts';
import { init } from './admin-campaign-preview.ts';

const mainKind = 'email_main_template';
const reminderKind = 'reminder_email_template';
const changeUrl = '/admin/campaigns/donationcampaign/example/change/';
const taskUrl = '/admin/django_celery_results/taskresult/123/change/';
let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;
let replaceStateSpy: MockInstance<History['replaceState']>;
let form: HTMLFormElement;
let showModalMock: ReturnType<typeof vi.fn<() => void>>;
let closeMock: ReturnType<typeof vi.fn<() => void>>;
let mainButton: HTMLButtonElement;
let reminderButton: HTMLButtonElement;

function response(payload: unknown, status = 200) {
    return new Response(JSON.stringify(payload), {
        status,
        headers: { 'Content-Type': 'application/json' },
    });
}

function statusFor(kind: string) {
    return document.querySelector<HTMLElement>(`[data-campaign-preview-status="${kind}"]`)!;
}

beforeEach(() => {
    document.body.innerHTML = `
        <form id="donationcampaign_form" action="${changeUrl}" method="post">
            <input name="csrfmiddlewaretoken" value="form-csrf-token">
            <input name="email_reminder_subject" value="Edited reminder subject">
            <input name="email_main_subject" value="Edited subject" required>
            <select name="email_main_template" required><option value="main.html" selected>Main</option></select>
            <button type="button" class="button" data-campaign-save-preview="${mainKind}">Save &amp; send preview</button>
            <span role="status" aria-live="polite" data-campaign-preview-status="${mainKind}"></span>
            <select name="reminder_email_template"><option value="">None</option><option value="reminder.html" selected>Reminder</option></select>
            <button type="button" class="button" data-campaign-save-preview="${reminderKind}">Save &amp; send preview</button>
            <span role="status" aria-live="polite" data-campaign-preview-status="${reminderKind}"></span>
            <button type="submit" name="_save">Save</button>
        </form>
        <dialog data-campaign-preview-dialog>
            <h2 id="campaign-preview-dialog-title">Preview requested</h2>
            <p data-campaign-preview-message></p>
            <a data-campaign-preview-task hidden>View delivery status</a>
            <button type="button" data-campaign-preview-close>Close</button>
        </dialog>
    `;
    const dialog = document.querySelector<HTMLDialogElement>('dialog')!;
    showModalMock = vi.fn(() => { dialog.open = true; });
    closeMock = vi.fn(() => { dialog.open = false; });
    dialog.showModal = showModalMock;
    dialog.close = closeMock;
    form = document.querySelector<HTMLFormElement>('form')!;
    mainButton = form.querySelector<HTMLButtonElement>(`[data-campaign-save-preview="${mainKind}"]`)!;
    reminderButton = form.querySelector<HTMLButtonElement>(`[data-campaign-save-preview="${reminderKind}"]`)!;
    fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response({
        message: 'Saved. Preview requested for admin@example.com.',
        change_url: changeUrl,
        task_results_url: taskUrl,
    }));
    vi.stubGlobal('fetch', fetchMock);
    replaceStateSpy = vi.spyOn(window.history, 'replaceState').mockImplementation(() => undefined);
    init({ formId: form.id });
});

afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
});

it.each([mainKind, reminderKind])('saves current form values and requests the %s preview without normal submission', async kind => {
    const submit = vi.fn((event: Event) => event.preventDefault());
    form.addEventListener('submit', submit);
    const button = kind === mainKind ? mainButton : reminderButton;
    button.click();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const [url, options] = fetchMock.mock.calls[0]!;
    expect(url).toBe(form.action);
    expect(options?.method).toBe('POST');
    expect(options?.credentials).toBe('same-origin');
    expect(options?.headers).toMatchObject({ Accept: 'application/json', 'X-CSRFToken': 'form-csrf-token' });
    const body = options?.body as FormData;
    expect(body.get('_save_preview')).toBe(kind);
    expect(body.get('email_main_subject')).toBe('Edited subject');
    expect(body.get('email_reminder_subject')).toBe('Edited reminder subject');
    expect(body.get('email_main_template')).toBe('main.html');
    expect(body.get('reminder_email_template')).toBe('reminder.html');
    expect(body.has('emails')).toBe(false);
    await vi.waitFor(() => expect(statusFor(kind).textContent).toContain('Preview requested for admin@example.com'));
    expect(statusFor(kind).querySelector('a')?.getAttribute('href')).toBe(new URL(taskUrl, location.href).href);
    expect(submit).not.toHaveBeenCalled();
    expect(form.querySelector<HTMLInputElement>('[name="email_main_subject"]')!.value).toBe('Edited subject');
    expect(mainButton.disabled).toBe(false);
    expect(reminderButton.disabled).toBe(false);
});

it('allows only one request while either preview is pending and restores both buttons', async () => {
    let finish!: (value: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise<Response>(resolve => { finish = resolve; }));
    mainButton.click();
    expect(mainButton.disabled).toBe(true);
    expect(reminderButton.disabled).toBe(true);
    expect(statusFor(mainKind).getAttribute('aria-busy')).toBe('true');
    reminderButton.click();
    mainButton.click();
    expect(fetchMock).toHaveBeenCalledOnce();
    finish(response({ message: 'Preview requested.', change_url: changeUrl, task_results_url: null }));
    await vi.waitFor(() => expect(mainButton.disabled).toBe(false));
    expect(reminderButton.disabled).toBe(false);
    expect(statusFor(mainKind).getAttribute('aria-busy')).toBe('false');
});

it('respects native validation and only requires a reminder selection for its own preview', async () => {
    const reminder = form.querySelector<HTMLSelectElement>('[name="reminder_email_template"]')!;
    reminder.value = '';
    const reminderSubject = form.querySelector<HTMLInputElement>('[name="email_reminder_subject"]')!;
    reminderSubject.value = '';
    reminderButton.click();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(reminder.required).toBe(false);
    expect(reminderSubject.required).toBe(false);
    mainButton.click();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    await vi.waitFor(() => expect(mainButton.disabled).toBe(false));
    form.querySelector<HTMLInputElement>('[name="email_main_subject"]')!.value = '';
    mainButton.click();
    expect(fetchMock).toHaveBeenCalledOnce();
});

it('keeps edits and displays safe server validation errors without navigation', async () => {
    fetchMock.mockResolvedValueOnce(response({ message: 'Please correct the form.', errors: { email_main_subject: ['<img src=x onerror=alert(1)>'], end_date: ['End must follow start.'] } }, 400));
    mainButton.click();
    await vi.waitFor(() => expect(statusFor(mainKind).textContent).toContain('End must follow start.'));
    expect(statusFor(mainKind).textContent).toContain('<img src=x onerror=alert(1)>');
    expect(statusFor(mainKind).querySelector('img')).toBeNull();
    expect(form.querySelector<HTMLInputElement>('[name="email_main_subject"]')!.value).toBe('Edited subject');
    expect(replaceStateSpy).not.toHaveBeenCalled();
    expect(showModalMock).not.toHaveBeenCalled();
    expect(mainButton.disabled).toBe(false);
});

it.each(['forbidden', 'html', 'network'])('reports %s failures and restores controls without retries', async failure => {
    if (failure === 'network') fetchMock.mockRejectedValueOnce(new Error('Network failure'));
    else if (failure === 'html') fetchMock.mockResolvedValueOnce(new Response('<html>Sign in</html>', { headers: { 'Content-Type': 'text/html' } }));
    else fetchMock.mockResolvedValueOnce(new Response('Forbidden', { status: 403 }));
    mainButton.click();
    await vi.waitFor(() => expect(statusFor(mainKind).textContent).not.toBe('Saving and requesting preview…'));
    await vi.waitFor(() => expect(mainButton.disabled).toBe(false));
    expect(statusFor(mainKind).textContent).toMatch(/permission|confirm/i);
    expect(reminderButton.disabled).toBe(false);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(replaceStateSpy).not.toHaveBeenCalled();
    expect(showModalMock).not.toHaveBeenCalled();
});

it('updates an add form to the saved change URL for repeated previews without reloading', async () => {
    form.action = '/admin/campaigns/donationcampaign/add/';
    mainButton.click();
    await vi.waitFor(() => expect(form.action).toBe(new URL(changeUrl, location.href).href));
    expect(replaceStateSpy).toHaveBeenCalledWith(null, '', new URL(changeUrl, location.href).href);
    await vi.waitFor(() => expect(mainButton.disabled).toBe(false));
    reminderButton.click();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1]![0]).toBe(new URL(changeUrl, location.href).href);
});

it('does not follow server-supplied off-site URLs or insert unsafe status links', async () => {
    fetchMock.mockResolvedValueOnce(response({ message: 'Preview requested.', change_url: 'https://evil.example/change/', task_results_url: 'javascript:alert(1)' }));
    const originalAction = form.action;
    mainButton.click();
    await vi.waitFor(() => expect(mainButton.disabled).toBe(false));
    expect(form.action).toBe(originalAction);
    expect(replaceStateSpy).not.toHaveBeenCalled();
    expect(showModalMock).not.toHaveBeenCalled();
    expect(statusFor(mainKind).querySelector('a')).toBeNull();
});

it.each([mainKind, reminderKind])('opens a dismissible success dialog after the %s preview is queued', async kind => {
    const dialog = document.querySelector<HTMLDialogElement>('dialog')!;
    const button = kind === mainKind ? mainButton : reminderButton;
    button.click();
    expect(showModalMock).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(showModalMock).toHaveBeenCalledOnce());
    expect(dialog.querySelector('[data-campaign-preview-message]')?.textContent).toBe('Saved. Preview requested for admin@example.com.');
    const taskLink = dialog.querySelector<HTMLAnchorElement>('[data-campaign-preview-task]')!;
    expect(taskLink.hidden).toBe(false);
    expect(taskLink.href).toBe(new URL(taskUrl, location.href).href);
    dialog.querySelector<HTMLButtonElement>('[data-campaign-preview-close]')!.click();
    expect(closeMock).toHaveBeenCalledOnce();
    expect(dialog.open).toBe(false);
});

it('shows a clear inline message when browser validation prevents a preview', () => {
    form.querySelector<HTMLInputElement>('[name="email_main_subject"]')!.value = '';
    mainButton.click();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(statusFor(mainKind).textContent).toContain('Complete the required campaign fields');
    expect(showModalMock).not.toHaveBeenCalled();
});


it('initializes preview buttons through the app controller glob and inert JSON context', async () => {
    const freshForm = form.cloneNode(true) as HTMLFormElement;
    form.replaceWith(freshForm);
    const declaration = document.createElement('script');
    declaration.type = 'application/json';
    declaration.dataset.speleodbController = 'admin-campaign-preview';
    declaration.textContent = JSON.stringify({ formId: freshForm.id });
    document.body.append(declaration);
    await initializeController(declaration);
    freshForm.querySelector<HTMLButtonElement>(`[data-campaign-save-preview="${mainKind}"]`)!.click();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    await vi.waitFor(() => expect(showModalMock).toHaveBeenCalledOnce());
});
