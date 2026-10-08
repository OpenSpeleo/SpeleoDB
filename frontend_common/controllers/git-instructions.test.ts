import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init } from './git-instructions.ts';
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
beforeEach(() => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    document.body.innerHTML = '<button id="btn_show_git_instructions"></button><div id="modal_git_instructions" style="display:none"><button class="btn_close"></button></div>';
});
afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ''; });
it('waits for load before opening the modal and prevents default on the trigger', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const pending = init();
    $('#btn_show_git_instructions').trigger('click');
    expect($('#modal_git_instructions')[0]!.style.display).toBe('none');
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    const event = $.Event('click');
    $('#btn_show_git_instructions').trigger(event);
    expect(event.isDefaultPrevented()).toBe(true);
    expect($('#modal_git_instructions')[0]!.style.display).toBe('flex');
});
it('uses actual layout visibility when deciding whether to close', async () => {
    await init();
    $('#btn_show_git_instructions').trigger('click');
    $('.btn_close').trigger('click');
    expect($('#modal_git_instructions')[0]!.style.display).toBe('flex');
    Object.defineProperty($('#modal_git_instructions')[0]!, 'offsetWidth', { configurable: true, value: 100 });
    $('.btn_close').trigger('click');
    expect($('#modal_git_instructions')[0]!.style.display).toBe('none');
});
it('accepts absent DOM and repeated initialization without returning cleanup', async () => {
    await init();
    await init();
    $('#btn_show_git_instructions').trigger('click');
    expect($('#modal_git_instructions')[0]!.style.display).toBe('flex');
    document.body.innerHTML = '';
    await expect(init()).resolves.toBeUndefined();
});
