/** Real jQuery, generated operation and HTTP coverage for shared autocomplete. */
import { startApiServer, setBrowserUrl, loadJQuery } from '../../../../frontend_common/test/api-server.ts';
import { attachUserAutocomplete } from './user_autocomplete.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
beforeAll(async () => { server = await startApiServer(); loadJQuery(); });
afterAll(async () => { await server.close(); });
beforeEach(() => { server.reset(); setBrowserUrl(server.origin); });
afterEach(() => { document.body.replaceChildren(); });

function installInput() {
    document.body.innerHTML = '<input id="user"><div id="user_suggestions" class="hidden"></div>';
    const $input = $('#user');
    const $suggestions = $('#user_suggestions');
    attachUserAutocomplete($input, $suggestions);
    return { $input, $suggestions };
}

it('renders a bare array with safe text and commits the selected email', async () => {
    server.reply({ json: [
        { email: 'alice@example.com', name: '<img src=x>' },
        { email: 'bob@example.com', name: 'Bob' },
    ] });
    const { $input, $suggestions } = installInput();
    $input.val('ali').trigger('input');
    await vi.waitFor(() => { expect($suggestions.children('div[data-index]').length).toBe(2); });
    expect(server.requests[0]).toMatchObject({ method: 'GET', path: '/api/v2/user/autocomplete/?query=ali' });
    expect($suggestions.text()).toContain('<img src=x>');
    expect($suggestions.find('img')).toHaveLength(0);
    $input.trigger($.Event('keydown', { key: 'Enter' }));
    expect($input.val()).toBe('alice@example.com');
    expect($suggestions.hasClass('hidden')).toBe(true);
});

it.each([
    { json: { data: [{ email: 'wrapped@example.com', name: 'W' }] } },
    { status: 403, json: { detail: 'Permission denied.' } },
])('keeps the dropdown hidden for an invalid envelope or HTTP error', async reply => {
    server.reply(reply);
    const { $input, $suggestions } = installInput();
    $input.val('query').trigger('input');
    await vi.waitFor(() => { expect(server.requests).toHaveLength(1); });
    await new Promise(resolve => setTimeout(resolve, 50));
    expect($suggestions.hasClass('hidden')).toBe(true);
    expect($suggestions.children('div[data-index]')).toHaveLength(0);
});

it('debounces rapid typing into one generated request', async () => {
    server.reply({ json: [] });
    const { $input } = installInput();
    $input.val('ali').trigger('input');
    $input.val('alic').trigger('input');
    $input.val('alice').trigger('input');
    await vi.waitFor(() => { expect(server.requests).toHaveLength(1); });
    expect(server.requests[0]!.path).toBe('/api/v2/user/autocomplete/?query=alice');
});

it('does not send queries shorter than three characters', async () => {
    const { $input, $suggestions } = installInput();
    $input.val('a').trigger('input');
    $input.val('al').trigger('input');
    await new Promise(resolve => setTimeout(resolve, 300));
    expect(server.requests).toHaveLength(0);
    expect($suggestions.hasClass('hidden')).toBe(true);
});

it('aborts a superseded request and ignores its late result', async () => {
    let release: (() => void) | undefined;
    server.handle(async request => {
        if (request.path.endsWith('query=old')) {
            await new Promise<void>(resolve => { release = resolve; });
            return { json: [{ email: 'old@example.com', name: 'Old' }] };
        }
        return { json: [{ email: 'new@example.com', name: 'New' }] };
    });
    const { $input, $suggestions } = installInput();
    $input.val('old').trigger('input');
    await vi.waitFor(() => { expect(server.requests).toHaveLength(1); });
    $input.val('new').trigger('input');
    await vi.waitFor(() => { expect($suggestions.text()).toContain('new@example.com'); });
    release?.();
    expect($suggestions.text()).not.toContain('old@example.com');
});
