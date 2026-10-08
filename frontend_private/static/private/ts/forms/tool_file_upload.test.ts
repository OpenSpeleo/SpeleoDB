import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

const jquerySource = readFileSync(path.join(process.cwd(), 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };
let originalAjax: FormTestJQuery['ajax'];
beforeAll(() => { (0, eval)(jquerySource); });
beforeEach(() => {
    vi.useFakeTimers();
    originalAjax = jqueryHost.jQuery.ajax;
    document.body.innerHTML = '<div id="modal_error"><span id="modal_error_txt"></span></div><div id="modal_success"><span id="modal_success_txt"></span></div>';
});
afterEach(() => {
    jqueryHost.jQuery.ajax = originalAjax;
    jqueryHost.jQuery(document).off();
    document.body.innerHTML = '';
    vi.useRealTimers();
});

import { attachToolFileUpload } from './tool_file_upload.ts';

function uploadControls(): void {
    document.body.insertAdjacentHTML('beforeend', '<div id="drop"></div><input type="file" id="file"><div id="filename"></div><div id="fileerror"></div><div id="status"></div><button id="action" disabled>Go</button>');
}
const uploadOptions = { dropZoneSelector: '#drop', fileInputSelector: '#file', fileNameSelector: '#filename', fileErrorSelector: '#fileerror', statusSelector: '#status', actionButtonSelector: '#action', allowedExtensions: ['.DMP'] };
function selectFile(file: File): void {
    const input = document.getElementById('file') as HTMLInputElement;
    Object.defineProperty(input, 'files', { configurable: true, value: [file] });
    jqueryHost.jQuery(input).trigger('change');
}

it('retains selected File identity, sanitizes extension policy, and clears selection on reset', () => {
    uploadControls();
    const selected = vi.fn();
    const tool = attachToolFileUpload({ ...uploadOptions, onFileSelected: selected });
    const file = new File(['data'], 'CAVE.DMP');
    selectFile(file);
    expect(tool.getFile()).toBe(file);
    expect(selected).toHaveBeenCalledWith(file);
    expect(jqueryHost.jQuery('#action').prop('disabled')).toBe(false);
    tool.setStatus('Working', 'red', 'bold');
    tool.reset();
    expect(tool.getFile()).toBeNull();
    expect(jqueryHost.jQuery('#status').text()).toBe('');
    expect(document.getElementById('status')!.style.fontWeight).toBe('bold');
});

it('rejects disallowed files and keeps the caller callback silent', () => {
    uploadControls();
    const selected = vi.fn();
    const tool = attachToolFileUpload({ ...uploadOptions, onFileSelected: selected });
    selectFile(new File(['data'], 'cave.txt'));
    expect(tool.getFile()).toBeNull();
    expect(selected).not.toHaveBeenCalled();
    expect(jqueryHost.jQuery('#drop').hasClass('invalid-file')).toBe(true);
});

it('keeps missing DOM errors and prevents drop propagation', () => {
    expect(() => attachToolFileUpload(uploadOptions)).toThrow('drop zone not found');
    uploadControls();
    attachToolFileUpload(uploadOptions);
    const event = new Event('dragover', { bubbles: true, cancelable: true });
    document.getElementById('drop')!.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    expect(jqueryHost.jQuery('#drop').hasClass('drag-over')).toBe(true);
});
