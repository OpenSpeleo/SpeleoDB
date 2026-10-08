import type { Mock } from 'vitest';
import type { StationTagsContext } from '../../ts-types/controllers/station-tags.ts';
import type { StationTagPresentation } from '../../ts-types/domain/project-presentation.ts';
import type { TaggedListOptions, TaggedListApi } from '../../ts-types/domain/forms/tagged-list.ts';
type TagOptions = Required<TaggedListOptions<StationTagPresentation>>;
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init as initialize } from './station-tags.ts';
import { attachTaggedEntityList } from '../../frontend_private/static/private/ts/forms/tagged_entity_list.ts';
import { FormModals } from '../../frontend_private/static/private/ts/forms/modals.ts';
vi.mock('../../frontend_private/static/private/ts/forms/tagged_entity_list.ts', () => ({ attachTaggedEntityList: vi.fn() }));
vi.mock('../../frontend_private/static/private/ts/forms/modals.ts', () => ({ FormModals: { showError: vi.fn() } }));
function init(context?: unknown) { return initialize(context as StationTagsContext); }
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
let listApi: {openEditModal: Mock<(id: string | number) => void>; openDeleteModal: Mock<(id: string | number) => void>};
function options() { return vi.mocked(attachTaggedEntityList).mock.calls.at(-1)![0] as TagOptions; }
beforeEach(() => {
    vi.clearAllMocks();
    listApi = { openEditModal: vi.fn(), openDeleteModal: vi.fn() };
    vi.mocked(attachTaggedEntityList).mockReturnValue(listApi as unknown as TaggedListApi);
    vi.stubGlobal('Urls', { 'api:v2:station-tag-detail': (id: string | number) => `/tags/${id}/` });
    document.body.innerHTML = '<table><tbody id="tags-table-body"></tbody></table><div id="tags-cards-container"></div><input id="edit-tag-id"><input id="edit-tag-name"><input id="edit-tag-color"><input id="custom-color-input" type="color"><div id="edit-tag-color-picker"></div><div id="delete-tag-info"></div><span id="delete-tag-station-count"></span>';
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = ''; });
it('immediately attaches list behavior with PUT editing and a lazy detail builder', () => {
    expect(init({ listEndpoint: '/tags/' })).toBeUndefined();
    expect(options()).toMatchObject({ listEndpoint: '/tags/', editMethod: 'PUT', entityLabel: 'tag', createModalTitle: 'Create New Tag', editModalTitle: 'Edit Tag' });
    expect(options().detailEndpointBuilder(7)).toBe('/tags/7/');
});
it('renders both empty layouts then escaped table/cards and binds each actual action receiver', () => {
    init({});
    options().renderList([], listApi as unknown as TaggedListApi);
    expect($('#tags-table-body').text()).toContain('No tags yet');
    expect($('#tags-cards-container').text()).toContain('No tags yet');
    const tag = { id: 7, name: '<unsafe>', color: '#ABCDEF', station_count: 1, creation_date: '2026-01-01' };
    options().renderList([tag], listApi as unknown as TaggedListApi);
    expect($('#tags-table-body').text()).toContain('<unsafe>');
    expect($('#tags-cards-container').text()).toContain('1 station');
    expect($('unsafe').length).toBe(0);
    $('#tags-table-body .btn-edit-tag').trigger('click');
    $('#tags-cards-container .btn-delete-tag').trigger('click');
    expect(listApi.openEditModal).toHaveBeenCalledExactlyOnceWith(7);
    expect(listApi.openEditModal.mock.contexts[0]).toBe(listApi);
    expect(listApi.openDeleteModal).toHaveBeenCalledExactlyOnceWith(7);
});
it('populates a case-insensitive palette and updates the selected input through palette and custom controls', () => {
    init({});
    options().resetEditModal();
    expect($('.tag-color-picker-option').length).toBe(20);
    expect($('#edit-tag-color').val()).toBe('#ef4444');
    options().openEditModalForEntity({ id: 7, name: 'Tag', color: '#EF4444' } as StationTagPresentation);
    expect($('.tag-color-picker-option.selected').length).toBe(1);
    $('.tag-color-picker-option').eq(1).trigger('click');
    expect($('#edit-tag-color').val()).toBe('#f97316');
    $('#custom-color-input').val('#abcdef').trigger('change');
    expect($('#edit-tag-color').val()).toBe('#ABCDEF');
    expect($('.tag-color-picker-option.selected').length).toBe(0);
});
it('validates required name and exact six-digit colors before collecting trimmed payload', () => {
    init({});
    expect(options().collectEditPayload()).toBeNull();
    expect(FormModals.showError).toHaveBeenLastCalledWith('Please enter a tag name');
    $('#edit-tag-name').val(' Tag ');
    expect(options().collectEditPayload()).toBeNull();
    expect(FormModals.showError).toHaveBeenLastCalledWith('Please select a color');
    $('#edit-tag-color').val('#abc');
    expect(options().collectEditPayload()).toBeNull();
    $('#edit-tag-color').val('#abcdef');
    expect(options().collectEditPayload()).toEqual({ name: 'Tag', color: '#abcdef' });
});
it('escapes delete presentation, repeats attachment and propagates helper errors', () => {
    init({});
    options().openDeleteModalForEntity({ name: '<unsafe>', color: 'invalid', station_count: null } as StationTagPresentation);
    expect($('#delete-tag-info').text()).toContain('<unsafe>');
    expect($('#delete-tag-info unsafe').length).toBe(0);
    expect($('#delete-tag-station-count').text()).toBe('0');
    init({});
    expect(attachTaggedEntityList).toHaveBeenCalledTimes(2);
    const error = new Error('List failed');
    vi.mocked(attachTaggedEntityList).mockImplementationOnce(() => { throw error; });
    expect(() => init({})).toThrow(error);
    expect(() => init()).toThrow(TypeError);
});
