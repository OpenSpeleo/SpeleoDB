import { readFileSync } from 'node:fs';
import path from 'node:path';

const jquerySource = readFileSync(path.join(process.cwd(), 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
let fields: typeof import('./experiment-fields.ts').ExperimentFields;
let $: JQueryStatic;
beforeEach(async () => {
    vi.resetModules();
    (0, eval)(jquerySource);
    $ = (globalThis as typeof globalThis & { jQuery: JQueryStatic }).jQuery;
    document.body.innerHTML = '<button id="add_field_btn"></button><div id="all_fields_container"></div><p id="no_fields_message">Empty</p>';
    fields = (await import('./experiment-fields.ts')).ExperimentFields;
});
afterEach(() => { $(document).off(); document.body.innerHTML = ''; vi.unstubAllGlobals(); });

it('captures jQuery during import and keeps a persistent counter across repeated wiring', () => {
    vi.stubGlobal('jQuery', vi.fn(() => { throw new Error('replacement'); }));
    expect(fields.initialize()).toBeUndefined();
    $('#add_field_btn').trigger('click');
    expect($('.field-item').attr('data-field-id')).toBe('1');
    $('.field-item').remove();
    fields.initialize();
    $('#add_field_btn').trigger('click');
    expect($('.field-item').map(function () { return $(this).attr('data-field-id'); }).get()).toEqual(['2', '3']);
});

it('validates edited and new names case-insensitively while retaining original values', () => {
    fields.initialize();
    $('#add_field_btn').trigger('click');
    document.body.insertAdjacentHTML('beforeend', '<div class="existing-field-item" data-field-id="abc"><input class="existing-field-name" value="Temperature"></div>');
    $('.field-name').val(' temperature ');
    expect(fields.validateUniqueFieldNames()).toBe(false);
    expect($('.existing-field-name').hasClass('border-rose-500')).toBe(true);
    expect($('.field-name').val()).toBe(' temperature ');
    $('.field-name').val('other');
    expect(fields.validateUniqueFieldNames()).toBe(true);
    // Existing-field styling is retained in this successful validation branch.
    expect($('.existing-field-name').hasClass('border-rose-500')).toBe(true);
});

it('keeps completeness errors and missing-input failures', () => {
    fields.initialize();
    $('#add_field_btn').trigger('click');
    expect(fields.validateFieldsComplete()).toEqual({ isValid: false, errorMessage: 'Some fields are incomplete. Please provide both a name and type for all new fields.' });
    $('.field-name').val('Field');
    $('.field-type').val('text');
    expect(fields.validateFieldsComplete()).toEqual({ isValid: true, errorMessage: '' });
    $('.field-name').remove();
    expect(() => fields.validateFieldsComplete()).toThrow();
});

it('creates inert tags, deduplicates case-insensitively and removes them through delegation', () => {
    fields.initialize();
    $('#add_field_btn').trigger('click');
    $('.field-type').val('select').trigger('change');
    expect($('.field-options-container').hasClass('hidden')).toBe(false);
    $('.field-option-input').val('<img src=x>, Second, SECOND').trigger('input');
    expect($('.tag-text').map(function () { return $(this).text(); }).get()).toEqual(['<img src=x>', 'Second']);
    expect(document.querySelector('.field-tags-container img')).toBeNull();
    $('.field-option-input').val('third').trigger($.Event('keydown', { key: 'Enter' }));
    expect($('.tag-text')).toHaveLength(3);
    $('.remove-tag').first().trigger('click');
    expect($('.tag-text')).toHaveLength(2);
});
