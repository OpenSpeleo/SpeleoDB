import type { FeedbackContext } from '../../ts-types/controllers/feedback.ts';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initialize } from './feedback.ts';

const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const fetchMock = vi.fn<(url: string, options: RequestInit) => Promise<{ ok: boolean; json(): Promise<unknown> }>>();
function init(context?: unknown) { return initialize(context as FeedbackContext); }

const fallbackMessage = 'Oops! There was a problem submitting your feedback';

beforeAll(() => {
    (0, eval)(jquery);
});

beforeEach(() => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    document.body.innerHTML = `
        <form id="feedback_form" method="post">
            <input name="score" value="1">
            <textarea name="message">Initial feedback</textarea>
            <button id="btn_submit">Submit</button>
        </form>
        <button class="feedback_score bg-slate-800 border-slate-500" data-score="1">One</button>
        <button class="feedback_score bg-slate-800 border-slate-500" data-score="5">Five</button>
        <div id="modal_success" style="display:none"><span id="modal_success_txt"></span></div>
        <div id="modal_error" style="display:none"><span id="modal_error_txt"></span></div>
        <div id="modal_confirmation" style="display:none"></div>
    `;
    fetchMock.mockReset().mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
    $('body').off('click');
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
});

async function submitFeedback() {
    const event = new MouseEvent('click', { bubbles: true, cancelable: true });
    document.getElementById('btn_submit')!.dispatchEvent(event);
    for (let turn = 0; turn < 4; turn++) await Promise.resolve();
    return event;
}

it('waits for load before binding and resolves without a cleanup result', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const pending = init({ endpoint: '/feedback/' });
    document.querySelector<HTMLElement>('[data-score="5"]')!.click();
    expect(document.querySelector<HTMLInputElement>('[name="score"]')!.value).toBe('1');
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    document.querySelector<HTMLElement>('[data-score="5"]')!.click();
    expect(document.querySelector<HTMLInputElement>('[name="score"]')!.value).toBe('5');
});

it('uses the clicked jQuery receiver to update score and exclusive selected styling', async () => {
    await init({ endpoint: '/feedback/' });
    const first = document.querySelector<HTMLElement>('[data-score="1"]')!;
    const last = document.querySelector<HTMLElement>('[data-score="5"]')!;
    first.click();
    last.click();
    expect(last.classList.contains('bg-indigo-500')).toBe(true);
    expect(first.classList.contains('bg-indigo-500')).toBe(false);
    expect(first.classList.contains('bg-slate-800')).toBe(true);
    expect(document.querySelector<HTMLInputElement>('[name="score"]')!.value).toBe('5');
});

it('submits native FormData with the form method, resets on success and shows the success modal', async () => {
    await init({ endpoint: '/feedback/' });
    document.querySelector<HTMLTextAreaElement>('[name="message"]')!.value = 'New feedback';
    document.querySelector<HTMLElement>('[data-score="5"]')!.click();
    const event = await submitFeedback();
    expect(event.defaultPrevented).toBe(true);
    expect(fetch).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/feedback/');
    expect(options.method).toBe('post');
    expect(options.headers).toEqual({ Accept: 'application/json' });
    expect(Object.keys(options)).toEqual(['method', 'body', 'headers']);
    expect(options.body).toBeInstanceOf(FormData);
    expect([...(options.body as FormData).entries()]).toEqual([['score', '5'], ['message', 'New feedback']]);
    expect(document.querySelector<HTMLInputElement>('[name="score"]')!.value).toBe('1');
    expect(document.querySelector<HTMLTextAreaElement>('[name="message"]')!.value).toBe('Initial feedback');
    expect(document.getElementById('modal_success')!.style.display).toBe('flex');
    expect(document.getElementById('modal_success_txt')!.textContent).toBe('Thanks for your feedback. We appreciate a lot!');
    document.body.click();
    expect(document.getElementById('modal_success')!.style.display).toBe('none');
});

// FormModals accepts trusted HTML, so API errors must be escaped at this caller.
it('renders API errors as inert text and joins messages in response order', async () => {
    const malicious = '<img src="missing" onerror="document.body.dataset.injectedEvent=\'yes\'"><em data-injected="feedback">unsafe</em>';
    fetchMock.mockResolvedValue({ ok: false, json: async () => ({ errors: [{ message: malicious }, { message: 'Second' }] }) });
    await init({ endpoint: '/feedback/' });
    await submitFeedback();
    const errorText = document.getElementById('modal_error_txt')!;
    expect(errorText.textContent).toBe(`${malicious}, Second`);
    expect(errorText.children).toHaveLength(0);
    expect(document.querySelector('#modal_error_txt [onerror], #modal_error_txt [data-injected]')).toBeNull();
    errorText.dispatchEvent(new Event('error'));
    expect(document.body.dataset.injectedEvent).toBeUndefined();
    expect(document.getElementById('modal_error')!.style.display).toBe('flex');
});

it.each([
    'Please enter your feedback',
    'Quotes "double" and \'single\'',
    '<strong>API error</strong>',
    'Salt & water &quot;label&quot; &#39;value&#39;',
])('preserves API error text without interpreting or decoding %s', async message => {
    fetchMock.mockResolvedValue({ ok: false, json: async () => ({ errors: [{ message }] }) });
    await init({ endpoint: '/feedback/' });
    await submitFeedback();
    const errorText = document.getElementById('modal_error_txt')!;
    expect(errorText.textContent).toBe(message);
    expect(errorText.children).toHaveLength(0);
});

it.each(['network', 'json', 'missing errors', 'invalid errors'])('shows the fallback and preserves form input on %s failure', async failure => {
    if (failure === 'network') fetchMock.mockRejectedValue(new Error('Offline'));
    if (failure === 'json') fetchMock.mockResolvedValue({ ok: true, json: async () => { throw new SyntaxError('Invalid JSON'); } });
    if (failure === 'missing errors') fetchMock.mockResolvedValue({ ok: false, json: async () => ({}) });
    if (failure === 'invalid errors') fetchMock.mockResolvedValue({ ok: false, json: async () => ({ errors: null }) });
    await init({ endpoint: '/feedback/' });
    document.querySelector<HTMLTextAreaElement>('[name="message"]')!.value = 'Keep this';
    await submitFeedback();
    expect(document.getElementById('modal_error_txt')!.textContent).toBe(fallbackMessage);
    expect(document.querySelector<HTMLTextAreaElement>('[name="message"]')!.value).toBe('Keep this');
});

it('binds duplicate submissions on repeated initialization', async () => {
    await init({ endpoint: '/first/' });
    await init({ endpoint: '/second/' });
    await submitFeedback();
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(['/first/', '/second/']);
});

it('rejects initialization without its submit button', async () => {
    document.getElementById('btn_submit')!.remove();
    await expect(init({ endpoint: '/feedback/' })).rejects.toThrow(TypeError);
});

it('catches missing context during submission rather than rejecting initialization', async () => {
    await expect(init()).resolves.toBeUndefined();
    await submitFeedback();
    expect(fetch).not.toHaveBeenCalled();
    expect(document.getElementById('modal_error_txt')!.textContent).toBe(fallbackMessage);
});
