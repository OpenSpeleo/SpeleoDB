import type { Mock } from 'vitest';
import type { CopyTokenContext } from '../../ts-types/controllers/copy-token.ts';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init } from './copy-token.ts';

const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const template = readFileSync(resolve('frontend_private/templates/pages/user/auth-token.html'), 'utf8');
const token = 'test-application-token';
let writeText: Mock<(value: string) => Promise<void>>;
let execCommand: Mock<(command: string) => boolean>;

beforeAll(() => {
    (0, eval)(jquery);
});

beforeEach(async () => {
    vi.useFakeTimers();
    document.body.innerHTML = template.replace(/{%.*?%}/gs, '').replace('{{ auth_token.key }}', token);
    writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    execCommand = vi.fn().mockReturnValue(true);
    document.execCommand = execCommand;
    const context = JSON.parse(document.querySelector<HTMLElement>('[data-speleodb-controller="copy-token"]')!.textContent) as CopyTokenContext;
    await init(context);
});

afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    delete (document as unknown as {execCommand?: unknown}).execCommand;
    document.body.innerHTML = '';
});

async function copyToken() {
    (document.getElementById('copy-token-btn') as HTMLButtonElement).click();
    await vi.advanceTimersByTimeAsync(0);
}

it('copies the displayed disabled input and resets its success feedback', async () => {
    const input = (document.getElementById('auth-token') as HTMLInputElement);
    const button = (document.getElementById('copy-token-btn') as HTMLButtonElement);
    expect(input.disabled).toBe(true);
    expect(button.type).toBe('button');
    expect(document.querySelector('label')!.htmlFor).toBe(input.id);
    await copyToken();
    expect(writeText).toHaveBeenCalledWith(token);
    expect(button.textContent.trim()).toBe('Copied!');
    expect(execCommand).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(2000);
    expect(button.textContent.trim()).toBe('Copy');
});

it('keeps info styling and restores the original icon after integration copy feedback', async () => {
    document.body.innerHTML = readFileSync(resolve('frontend_private/templates/pages/experiment/gis_integration.html'), 'utf8')
        .replace(/{%.*?%}/gs, '');
    const context = JSON.parse(document.querySelector<HTMLElement>('[data-speleodb-controller="copy-token"]')!.textContent) as CopyTokenContext;
    delete context.waitForWindowLoad;
    await init(context);
    const button = (document.getElementById('copy-btn') as HTMLButtonElement);
    const icon = document.getElementById('copy-icon')!;
    const originalIcon = icon.innerHTML;
    const originalClass = button.className;
    button.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(button.textContent.trim()).toBe('Copied!');
    expect(button.className).toBe(originalClass);
    await vi.advanceTimersByTimeAsync(2000);
    expect(button.textContent.trim()).toBe('Copy');
    expect(button.className).toBe(originalClass);
    expect(icon.innerHTML).toBe(originalIcon);
});

it('keeps the unavailable surface-network copy control disabled', async () => {
    document.body.innerHTML = readFileSync(resolve('frontend_private/templates/pages/surface_network/gis_integration.html'), 'utf8')
        .replace(/{%.*?%}/gs, '');
    const context = JSON.parse(document.querySelector<HTMLElement>('[data-speleodb-controller="copy-token"]')!.textContent) as CopyTokenContext;
    delete context.waitForWindowLoad;
    await init(context);
    const button = (document.getElementById('copy-btn') as HTMLButtonElement);
    expect(button.disabled).toBe(true);
    button.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(writeText).not.toHaveBeenCalled();
    expect(button.textContent.trim()).toBe('Unavailable');
});

it.each(['unavailable', 'denied'])('uses the fallback when clipboard access is %s', async reason => {
    if (reason === 'unavailable') (navigator as unknown as {clipboard: undefined}).clipboard = undefined;
    else writeText.mockRejectedValue(new Error('Clipboard denied'));
    execCommand.mockImplementation(command => {
        expect(command).toBe('copy');
        expect(document.querySelector('textarea')!.value).toBe(token);
        return true;
    });
    await copyToken();
    expect(execCommand).toHaveBeenCalledOnce();
    expect(document.querySelector('textarea')!).toBeNull();
    expect(document.getElementById('copy-token-text')!.textContent).toBe('Copied!');
});

it('reports failed copying without showing success and allows a retry', async () => {
    writeText.mockRejectedValueOnce(new Error('Clipboard denied'));
    execCommand.mockReturnValue(false);
    await copyToken();
    expect(document.getElementById('copy-token-text')!.textContent).toBe('Failed');
    await vi.advanceTimersByTimeAsync(2000);
    expect(document.getElementById('copy-token-text')!.textContent).toBe('Copy');
    await copyToken();
    expect(document.getElementById('copy-token-text')!.textContent).toBe('Copied!');
});

it('does not copy an empty token', async () => {
    (document.getElementById('auth-token') as HTMLInputElement).value = '';
    await copyToken();
    expect(writeText).not.toHaveBeenCalled();
    expect(execCommand).not.toHaveBeenCalled();
});

it('preserves copying text content for existing integration pages', async () => {
    const source = document.createElement('code');
    source.id = 'integration-url';
    source.textContent = ' https://example.com/integration/ ';
    const button = document.createElement('button');
    button.id = 'copy-integration';
    button.textContent = 'Copy';
    document.body.append(source, button);
    await init({ copyButtons: [{ button: '#copy-integration', value: '#integration-url', text: '#copy-integration' }] });
    button.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(writeText).toHaveBeenCalledWith('https://example.com/integration/');
    expect(button.textContent).toBe('Copied!');
});

it('waits only when requested, preserves missing-context rejection and repeated attachment', async () => {
    await expect(init(undefined as unknown as CopyTokenContext)).rejects.toThrow(TypeError);
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const descriptor = { button: '#copy-token-btn', value: '#auth-token', text: '#copy-token-text' };
    const pending = init({ waitForWindowLoad: true, copyButtons: [descriptor] });
    await copyToken();
    expect(writeText).toHaveBeenCalledTimes(1);
    window.dispatchEvent(new Event('load'));
    await pending;
    await copyToken();
    expect(writeText).toHaveBeenCalledTimes(3);
    vi.restoreAllMocks();
});

it('keeps token confirmation submission and cancel behavior', async () => {
    document.body.innerHTML = '<form id="form"></form><div id="modal" style="display:none"><button id="cancel"></button><button id="confirm"></button></div>';
    const form = (document.getElementById('form') as HTMLFormElement);
    const submitForm = vi.fn();
    form.submit = submitForm;
    await init({ tokenModal: { form: '#form', modal: '#modal', cancel: '#cancel', confirm: '#confirm' } });
    const submit = new Event('submit', { cancelable: true });
    form.dispatchEvent(submit);
    expect(submit.defaultPrevented).toBe(true);
    expect(document.body.style.overflow).toBe('hidden');
    document.getElementById('cancel')!.click();
    expect(document.body.style.overflow).toBe('');
    form.dispatchEvent(new Event('submit', { cancelable: true }));
    document.getElementById('confirm')!.click();
    expect(submitForm).toHaveBeenCalledOnce();
    expect(document.getElementById('modal')!.style.display).toBe('none');
});
