import type Sortable from 'sortablejs';
import type { MockInstance } from 'vitest';
import type { ExperimentFormContext, ExperimentFormPayload } from '../../ts-types/controllers/experiment-form.ts';
import type { EntityId } from '../../ts-types/domain/identifiers.ts';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init } from './experiment-form.ts';
import { ExperimentFields } from '../../frontend_private/static/private/ts/experiment-fields.ts';
import { FormModals } from '../../frontend_private/static/private/ts/forms/modals.ts';
import { showAjaxErrorModal } from '../../frontend_private/static/private/ts/forms/ajax_errors.ts';
vi.mock('../../frontend_private/static/private/ts/experiment-fields.ts', () => ({ ExperimentFields: { initialize: vi.fn(), validateFieldsComplete: vi.fn(), validateUniqueFieldNames: vi.fn() } }));
vi.mock('../../frontend_private/static/private/ts/forms/modals.ts', () => ({ FormModals: { showError: vi.fn(), showSuccess: vi.fn() } }));
interface Request { data: string; beforeSend(xhr: { setRequestHeader(name: string, value: string): void }): void; success(data: { id: EntityId }): void }
let requests: Request[];
let ajax: MockInstance<JQueryStatic['ajax']>;
let timeout: MockInstance<typeof window.setTimeout>;
const sortable = vi.fn<(element: HTMLElement, options: Sortable.Options) => unknown>();
const fields = vi.mocked(ExperimentFields);
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    requests = [];
    ajax = vi.spyOn($, 'ajax').mockImplementation(settings => { requests.push(settings as unknown as Request); return {} as JQuery.jqXHR<unknown>; });
    timeout = vi.spyOn(window, 'setTimeout').mockReturnValue(1 as unknown as ReturnType<typeof setTimeout>);
    window.Sortable = { create: sortable } as unknown as typeof window.Sortable;
    fields.validateFieldsComplete.mockReturnValue({ isValid: true, errorMessage: '' });
    fields.validateUniqueFieldNames.mockReturnValue(true);
    document.body.innerHTML = '<form id="experiment"><input name="name" value="Experiment"><input name="csrfmiddlewaretoken" value="csrf"></form><button id="btn_submit"></button><div id="all_fields_container"></div>';
});
afterEach(() => { vi.restoreAllMocks(); Reflect.deleteProperty(window, 'Sortable'); document.body.innerHTML = ''; });
const context: ExperimentFormContext = { mode: 'create', formId: 'experiment', endpoint: '/experiment/', method: 'POST', successMessage: 'Saved' };
it('waits for load and initializes fields before configuring sortable create rows', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const pending = init(context);
    expect(fields.initialize).not.toHaveBeenCalled();
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    expect(sortable).toHaveBeenCalledWith(document.getElementById('all_fields_container'), { animation: 150, handle: '.drag-handle', ghostClass: 'sortable-ghost', dragClass: 'sortable-drag', forceFallback: true, fallbackClass: 'sortable-fallback', draggable: '.mandatory-field-item, .field-item' });
    expect(fields.initialize.mock.invocationCallOrder[0]!).toBeLessThan(sortable.mock.invocationCallOrder[0]!);
});
it('checks completeness before duplicates and prevents submission for either error', async () => {
    await init(context);
    fields.validateFieldsComplete.mockReturnValue({ isValid: false, errorMessage: 'Incomplete' });
    $('#btn_submit').trigger('click');
    expect(FormModals.showError).toHaveBeenLastCalledWith('Incomplete');
    expect(fields.validateUniqueFieldNames).not.toHaveBeenCalled();
    fields.validateFieldsComplete.mockReturnValue({ isValid: true, errorMessage: '' });
    fields.validateUniqueFieldNames.mockReturnValue(false);
    $('#btn_submit').trigger('click');
    expect(FormModals.showError).toHaveBeenLastCalledWith('Duplicate field names detected. Each field must have a unique name. Please check the highlighted fields.');
    expect(ajax).not.toHaveBeenCalled();
});
it('rejects exactly two mandatory fields before submitting', async () => {
    $('#all_fields_container').html('<div class="mandatory-field-item" data-field-name="Date" data-field-type="date" data-field-required="true"></div><div class="mandatory-field-item" data-field-name="Email" data-field-type="text" data-field-required="true"></div>');
    await init(context);
    $('#btn_submit').trigger('click');
    expect(FormModals.showError).toHaveBeenCalledWith('Please add at least one custom field for data collection.');
    expect(ajax).not.toHaveBeenCalled();
});
it('collects ordered mandatory and new fields, trimmed names and choice text into JSON', async () => {
    $('#all_fields_container').html('<div class="mandatory-field-item" data-field-name="Date" data-field-type="date" data-field-required="true"></div><div class="field-item"><input class="field-name" value=" Choice "><select class="field-type"><option value="select">Select</option></select><input type="checkbox" class="field-required" checked><div class="field-tags-container"><span class="tag-text">Low</span><span class="tag-text">High</span></div></div><div class="field-item"><input class="field-name" value=""><select class="field-type"><option value="text">Text</option></select></div>');
    // Add a third valid field: the legacy create guard checks count, not field ownership.
    $('#all_fields_container').append('<div class="mandatory-field-item" data-field-name="Email" data-field-type="text" data-field-required="true"></div>');
    await init(context);
    $('#btn_submit').trigger('click');
    const request = requests[0]!;
    expect(request).toMatchObject({ url: '/experiment/', method: 'POST', contentType: 'application/json; charset=utf-8', cache: false, error: showAjaxErrorModal });
    expect((JSON.parse(request.data) as ExperimentFormPayload).experiment_fields).toEqual([{ name: 'Date', type: 'date', required: true }, { name: 'Choice', type: 'select', required: true, options: ['Low', 'High'] }, { name: 'Email', type: 'text', required: true }]);
    const xhr = { setRequestHeader: vi.fn() };
    request.beforeSend(xhr);
    expect(xhr.setRequestHeader).toHaveBeenCalledWith('X-CSRFToken', 'csrf');
    request.success({ id: 1 });
    expect(FormModals.showSuccess).toHaveBeenCalledWith('Saved');
    expect(timeout.mock.calls).toContainEqual([expect.any(Function), 2000]);
});
it('preserves existing IDs and options and omits empty edit fields', async () => {
    $('#all_fields_container').html('<div class="existing-field-item" data-field-id="field-id" data-field-type="select" data-field-required="true"><input class="existing-field-name" value=" Existing "></div>');
    $('.existing-field-item').data('field-options', '["A","B"]');
    await init({ ...context, mode: 'edit' });
    expect(sortable.mock.calls[0]![1].draggable).toBe('.existing-field-item, .field-item');
    $('#btn_submit').trigger('click');
    expect((JSON.parse(requests[0]!.data) as ExperimentFormPayload).experiment_fields).toEqual([{ id: 'field-id', name: 'Existing', type: 'select', required: true, options: ['A', 'B'] }]);
    $('#all_fields_container').empty();
    $('#btn_submit').trigger('click');
    expect(JSON.parse(requests[1]!.data)).not.toHaveProperty('experiment_fields');
});
it('repeats submit handlers and rejects a missing Sortable only when its container exists', async () => {
    await init({ ...context, mode: 'edit' });
    await init({ ...context, mode: 'edit' });
    $('#btn_submit').trigger('click');
    expect(ajax).toHaveBeenCalledTimes(2);
    Reflect.deleteProperty(window, 'Sortable');
    await expect(init(context)).rejects.toThrow(TypeError);
    $('#all_fields_container').remove();
    await expect(init(context)).resolves.toBeUndefined();
});
