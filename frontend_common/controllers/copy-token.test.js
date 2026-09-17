import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init } from './copy-token.js';

const jquery = readFileSync(resolve('frontend_public/static/js/vendors/jquery-3.7.1.js'), 'utf8');
const template = readFileSync(resolve('frontend_private/templates/pages/user/auth-token.html'), 'utf8');
const token = 'test-application-token';
let writeText;
let execCommand;

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
    const context = JSON.parse(document.querySelector('[data-speleodb-controller="copy-token"]').textContent);
    await init(context);
});

afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    delete document.execCommand;
    document.body.innerHTML = '';
});

async function copyToken() {
    document.getElementById('copy-token-btn').click();
    await vi.advanceTimersByTimeAsync(0);
}

it('copies the displayed disabled input and resets its success feedback', async () => {
    const input = document.getElementById('auth-token');
    const button = document.getElementById('copy-token-btn');
    expect(input.disabled).toBe(true);
    expect(button.type).toBe('button');
    expect(document.querySelector('label').htmlFor).toBe(input.id);
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
    const context = JSON.parse(document.querySelector('[data-speleodb-controller="copy-token"]').textContent);
    delete context.waitForWindowLoad;
    await init(context);
    const button = document.getElementById('copy-btn');
    const icon = document.getElementById('copy-icon');
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
    const context = JSON.parse(document.querySelector('[data-speleodb-controller="copy-token"]').textContent);
    delete context.waitForWindowLoad;
    await init(context);
    const button = document.getElementById('copy-btn');
    expect(button.disabled).toBe(true);
    button.click();
    await vi.advanceTimersByTimeAsync(0);
    expect(writeText).not.toHaveBeenCalled();
    expect(button.textContent.trim()).toBe('Unavailable');
});

it.each(['unavailable', 'denied'])('uses the fallback when clipboard access is %s', async reason => {
    if (reason === 'unavailable') navigator.clipboard = undefined;
    else writeText.mockRejectedValue(new Error('Clipboard denied'));
    execCommand.mockImplementation(command => {
        expect(command).toBe('copy');
        expect(document.querySelector('textarea').value).toBe(token);
        return true;
    });
    await copyToken();
    expect(execCommand).toHaveBeenCalledOnce();
    expect(document.querySelector('textarea')).toBeNull();
    expect(document.getElementById('copy-token-text').textContent).toBe('Copied!');
});

it('reports failed copying without showing success and allows a retry', async () => {
    writeText.mockRejectedValueOnce(new Error('Clipboard denied'));
    execCommand.mockReturnValue(false);
    await copyToken();
    expect(document.getElementById('copy-token-text').textContent).toBe('Failed');
    await vi.advanceTimersByTimeAsync(2000);
    expect(document.getElementById('copy-token-text').textContent).toBe('Copy');
    await copyToken();
    expect(document.getElementById('copy-token-text').textContent).toBe('Copied!');
});

it('does not copy an empty token', async () => {
    document.getElementById('auth-token').value = '';
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
