import type { Mock } from 'vitest';
import type { EntityCrudContext, CreatedEntity } from '../../ts-types/controllers/entity-crud.ts';
import type { FormPayload, EntityCrudOptions } from '../../ts-types/domain/forms/crud.ts';
import type { ApplicationUrls } from '../../ts-types/browser/urls.d.ts';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initialize } from './entity-crud.ts';
import { initColorPicker } from '../../frontend_private/static/private/ts/color-picker.ts';
import { attachEntityCrudForm } from '../../frontend_private/static/private/ts/forms/entity_crud_form.ts';
import { FormModals } from '../../frontend_private/static/private/ts/forms/modals.ts';

vi.mock('../../frontend_private/static/private/ts/color-picker.ts', () => ({ initColorPicker: vi.fn() }));
vi.mock('../../frontend_private/static/private/ts/forms/entity_crud_form.ts', () => ({ attachEntityCrudForm: vi.fn() }));
vi.mock('../../frontend_private/static/private/ts/forms/modals.ts', () => ({ FormModals: { showError: vi.fn() } }));
function init(context?: unknown) { return initialize(context as EntityCrudContext); }
const attachment = vi.mocked(attachEntityCrudForm) as unknown as Mock<(options: EntityCrudOptions<CreatedEntity>) => unknown>;
const picker = vi.mocked(initColorPicker);
const routes: Partial<Record<'private:entity', Mock<(id: number) => string>>> = {};
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    document.body.innerHTML = '<form id="entity"><input type="checkbox" name="active" checked><input type="checkbox" name="public"></form><button id="add_sensor_btn"></button><div id="sensors_container"></div>';
    delete routes['private:entity']; window.Urls = routes as unknown as ApplicationUrls;
});
afterEach(() => { $(document).off('click'); vi.restoreAllMocks(); Reflect.deleteProperty(window, 'Urls'); document.body.innerHTML = ''; });

it('waits for load then forwards configuration without enabling absent optional callbacks', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const context = { formId: 'entity', endpoint: '/entity/', method: 'PUT', successMessage: 'Saved', reloadOnSuccess: true };
    const pending = init(context);
    expect(attachEntityCrudForm).not.toHaveBeenCalled();
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    expect(attachment.mock.calls[0]![0]).toEqual({ ...context, successRedirect: undefined, redirectFromResponse: undefined, beforeSubmit: undefined, serialize: undefined });
    expect(initColorPicker).not.toHaveBeenCalled();
});
it('initializes color selection before attaching the form', async () => {
    await init({ colorPicker: true });
    expect(initColorPicker).toHaveBeenCalledWith({ preview: '#color-preview', hiddenInput: '#color-value', nativePicker: '#color-picker', pickerBtn: '#color-picker-btn', hexInput: '#color-hex-input', presets: '.color-preset' });
    expect(picker.mock.invocationCallOrder[0]!).toBeLessThan(attachment.mock.invocationCallOrder[0]!);
});
it('validates the required value before collecting trimmed sensor rows and preserves payload identity', async () => {
    await init({ requiredField: 'name', requiredMessage: 'Name required', sensorRows: true });
    const { beforeSubmit } = attachment.mock.calls[0]![0];
    $('#add_sensor_btn').trigger('click');
    $('#add_sensor_btn').trigger('click');
    expect($('.sensor-item').length).toBe(2);
    $('.sensor-name').first().val('  Sensor A  ');
    $('.sensor-notes').first().val('  Notes  ');
    const invalid = { name: ' ' };
    expect(beforeSubmit!(invalid)).toBe(false);
    expect(invalid).not.toHaveProperty('sensors');
    expect(FormModals.showError).toHaveBeenCalledWith('Name required');
    const payload: FormPayload = { name: 'Fleet' };
    expect(beforeSubmit!(payload)).toBe(true);
    expect(payload.sensors).toEqual([{ name: 'Sensor A', notes: 'Notes' }]);
    $('.remove-sensor-btn').first().trigger('click');
    const empty = { name: 'Fleet' };
    expect(beforeSubmit!(empty)).toBe(true);
    expect(empty).not.toHaveProperty('sensors');
});
it('serializes all named checkboxes and resolves redirect routes only when used', async () => {
    await init({ formId: 'entity', serializeCheckboxes: true, redirectRoute: 'private:entity' });
    const { serialize, redirectFromResponse } = attachment.mock.calls[0]![0];
    const payload: FormPayload = { name: 'Fleet' };
    expect(JSON.parse(serialize!(payload))).toEqual({ name: 'Fleet', active: true, public: false });
    expect(payload.active).toBe(true);
    expect(() => redirectFromResponse!({ id: 3 })).toThrow('Missing Django URL route: private:entity');
    routes['private:entity'] = vi.fn().mockReturnValue('/entity/3/');
    expect(redirectFromResponse!({ id: 3 })).toBe('/entity/3/');
    expect(routes['private:entity']).toHaveBeenCalledWith(3);
});
it('repeats sensor handlers, ignores helper return promises and rejects missing context', async () => {
    attachment.mockReturnValue(new Promise(() => {}));
    await init({ sensorRows: true });
    await init({ sensorRows: true });
    $('#add_sensor_btn').trigger('click');
    expect($('.sensor-item').length).toBe(2);
    expect($('.sensor-item').map(function () { return this.dataset.sensorId; }).get()).toEqual(['1', '1']);
    await expect(init()).rejects.toThrow(TypeError);
});
it('propagates attachment errors', async () => {
    const error = new Error('Attachment failed');
    attachment.mockImplementationOnce(() => { throw error; });
    await expect(init({})).rejects.toBe(error);
});
