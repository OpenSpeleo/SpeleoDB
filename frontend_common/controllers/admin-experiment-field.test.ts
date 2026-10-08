import type { AdminExperimentFieldContext } from '../../ts-types/controllers/admin-experiment-field.ts';
import type { AdminExperimentFields } from '../../ts-types/domain/admin-experiment-fields.ts';
import { init } from './admin-experiment-field.ts';

function mountFields(fields: AdminExperimentFields = {}) {
    document.body.innerHTML = `
        <textarea id="experiment-fields"></textarea>
        <div id="custom-fields-container"></div>
        <p id="no-fields-msg">No fields</p>
        <button id="add-field-btn" type="button">Add field</button>
    `;
    (document.getElementById('experiment-fields') as HTMLTextAreaElement).value = JSON.stringify(fields);
}

function savedFields() {
    return JSON.parse((document.getElementById('experiment-fields') as HTMLTextAreaElement).value) as AdminExperimentFields;
}

beforeEach(() => {
    mountFields();
});

afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
});

it('initializes immediately, returns undefined, and displays the empty state', () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    expect(init({ textareaId: 'experiment-fields' })).toBeUndefined();
    expect(document.getElementById('no-fields-msg')!.style.display).toBe('block');
});

it('loads custom fields as immutable while preserving mandatory records and hashes on save', () => {
    const mandatory = { name: 'Date', type: 'date', hash: 'mandatory-hash' };
    const custom = { name: 'Quality', type: 'select', required: true, options: ['Low', 'High'], hash: 'custom-hash' };
    mountFields({ measurement_date: mandatory, submitter_email: { type: 'text' }, quality: custom });
    init({ textareaId: 'experiment-fields' });
    const fields = document.querySelectorAll<HTMLElement>('.exp-field-item');
    expect(fields).toHaveLength(1);
    expect(fields[0]!.dataset.slug).toBe('quality');
    expect(fields[0]!.dataset.isExisting).toBe('true');
    expect(fields[0]!.querySelector<HTMLInputElement>('.field-name')!.readOnly).toBe(true);
    expect(fields[0]!.querySelector<HTMLSelectElement>('.field-type')!.disabled).toBe(true);
    expect(fields[0]!.querySelector<HTMLInputElement>('.field-required')!.disabled).toBe(true);
    expect(fields[0]!.querySelector<HTMLInputElement>('.field-options')!.value).toBe('Low, High');
    expect(fields[0]!.querySelector<HTMLButtonElement>('.remove-btn')!).toBeNull();
    expect(document.getElementById('no-fields-msg')!.style.display).toBe('none');
    document.getElementById('add-field-btn')!.click();
    expect(savedFields()).toEqual({ measurement_date: mandatory, submitter_email: { type: 'text' }, quality: custom });
});

it('saves new named fields, trims choices, toggles choice visibility and removes fields', () => {
    init({ textareaId: 'experiment-fields' });
    document.getElementById('add-field-btn')!.click();
    expect(savedFields()).toEqual({});
    const field = document.querySelector<HTMLElement>('.exp-field-item')!;
    const name = field.querySelector<HTMLInputElement>('.field-name')!;
    const type = field.querySelector<HTMLSelectElement>('.field-type')!;
    name.value = '  Quality  ';
    type.value = 'select';
    type.dispatchEvent(new Event('change'));
    expect(field.querySelector<HTMLElement>('.options-container')!.style.display).toBe('block');
    field.querySelector<HTMLInputElement>('.field-required')!.checked = true;
    const options = field.querySelector<HTMLInputElement>('.field-options')!;
    options.value = ' Low, , High, ';
    options.dispatchEvent(new Event('input'));
    const saved = savedFields();
    expect(Object.keys(saved)).toHaveLength(1);
    expect(Object.keys(saved)[0]).toMatch(/^temp_\d+_/);
    expect(Object.values(saved)).toEqual([{ name: 'Quality', type: 'select', required: true, options: ['Low', 'High'] }]);
    type.value = 'text';
    type.dispatchEvent(new Event('change'));
    expect(field.querySelector<HTMLElement>('.options-container')!.style.display).toBe('none');
    expect(Object.values(savedFields())[0]).not.toHaveProperty('options');
    field.querySelector<HTMLButtonElement>('.remove-btn')!.click();
    expect(savedFields()).toEqual({});
    expect(document.getElementById('no-fields-msg')!.style.display).toBe('block');
});

it('logs malformed existing JSON without throwing and can save new fields afterwards', () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    (document.getElementById('experiment-fields') as HTMLTextAreaElement).value = '{';
    expect(() => init({ textareaId: 'experiment-fields' })).not.toThrow();
    expect(error).toHaveBeenCalledWith('Error parsing existing fields:', expect.any(SyntaxError));
    document.getElementById('add-field-btn')!.click();
    expect(savedFields()).toEqual({});
});

it('throws synchronously for missing context or add button but catches a missing textarea', () => {
    expect(() => init(undefined as unknown as AdminExperimentFieldContext)).toThrow(TypeError);
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    init({ textareaId: 'absent' });
    expect(error).toHaveBeenCalledWith('Error parsing existing fields:', expect.any(TypeError));
    document.getElementById('add-field-btn')!.remove();
    expect(() => init({ textareaId: 'experiment-fields' })).toThrow(TypeError);
});

it('duplicates existing rows and add handlers when initialized twice', () => {
    mountFields({ quality: { name: 'Quality', type: 'text' } });
    init({ textareaId: 'experiment-fields' });
    init({ textareaId: 'experiment-fields' });
    expect(document.querySelectorAll<HTMLElement>('.exp-field-item')).toHaveLength(2);
    document.getElementById('add-field-btn')!.click();
    expect(document.querySelectorAll<HTMLElement>('.exp-field-item')).toHaveLength(4);
});

// User-controlled values must remain text in both HTML attributes and slug markup.
it('keeps names, options and slugs inert when they contain markup and event attributes', () => {
    const eventPayload = "document.body.dataset.injectedEvent='yes'";
    const slug = `quality<img src="missing" onerror="${eventPayload}">`;
    const name = `name" onfocus="${eventPayload}" data-injected="name`;
    const option = `option" onfocus="${eventPayload}" data-injected="option`;
    mountFields({ [slug]: { name, type: 'select', options: [option] } });
    init({ textareaId: 'experiment-fields' });
    const nameInput = document.querySelector<HTMLInputElement>('.field-name')!;
    const optionsInput = document.querySelector<HTMLInputElement>('.field-options')!;
    expect(nameInput.value).toBe(name);
    expect(optionsInput.value).toBe(option);
    expect(document.querySelector<HTMLElement>('.exp-field-item')!.dataset.slug).toBe(slug);
    expect(document.querySelector('code')!.textContent).toBe(`Slug: ${slug}`);
    expect(document.querySelector('[data-injected], [onfocus], [onerror], img')).toBeNull();
    nameInput.dispatchEvent(new FocusEvent('focus'));
    optionsInput.dispatchEvent(new FocusEvent('focus'));
    expect(document.body.dataset.injectedEvent).toBeUndefined();
});

it.each([
    'pH Level (mg/L-N)',
    'Quotes "double" and \'single\'',
    '<strong>label</strong>',
    'Salt & water &quot;label&quot; &#39;value&#39;',
])('preserves the displayed and serialized field value %s', payload => {
    const slug = `field-${payload}`;
    const field = { name: payload, type: 'select', required: true, options: [payload, 'Second'], hash: 'unchanged-hash' };
    mountFields({ [slug]: field });
    init({ textareaId: 'experiment-fields' });
    expect(document.querySelector<HTMLInputElement>('.field-name')!.value).toBe(payload);
    expect(document.querySelector<HTMLInputElement>('.field-options')!.value).toBe(`${payload}, Second`);
    expect(document.querySelector('code')!.textContent).toBe(`Slug: ${slug}`);
    expect(document.querySelector('code')!.children).toHaveLength(0);
    document.getElementById('add-field-btn')!.click();
    expect(savedFields()).toEqual({ [slug]: field });
});
