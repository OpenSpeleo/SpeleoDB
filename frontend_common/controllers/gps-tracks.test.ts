import type { Mock } from 'vitest';
import type { ApplicationUrls } from '../../ts-types/browser/urls.d.ts';
import type { GISListRecord, GISListContext, GISUploadListContext, GISUploadErrorDetails } from '../../ts-types/controllers/gis-lists.ts';
import type { TaggedListApi, TaggedListOptions } from '../../ts-types/domain/forms/tagged-list.ts';
import { buildTrackListMarkup } from './gps-tracks.ts';

function track(overrides: Partial<GISListRecord> = {}) {
    return {
        id: '11111111-1111-4111-8111-111111111111',
        name: 'Cenote Traverse',
        color: '#377eb8',
        created_by: 'creator@example.com',
        user_permission_level_label: 'READ_ONLY',
        can_write: false,
        can_delete: false,
        creation_date: '2026-08-09T12:00:00Z',
        ...overrides,
    };
}

function render(tracks: GISListRecord[]) {
    const { tableHtml, cardsHtml } = buildTrackListMarkup(
        tracks,
        '/static/private/media/right_arrow.svg',
    );
    document.body.innerHTML = `
        <table><tbody id="tracks-table-body">${tableHtml}</tbody></table>
        <div id="tracks-cards-container">${cardsHtml}</div>`;
}

beforeEach(() => {
    globalThis.Urls = {
        'api:v2:gps-track-export-gpx': id => `/api/v2/gps_tracks/${id}/export/gpx/`,
        'private:gps_track_details': id => `/private/gps-track/${id}/`,
    } as ApplicationUrls;
});

afterEach(() => {
    document.body.innerHTML = '';
    Reflect.deleteProperty(globalThis, 'Urls');
});

describe('GPS Tracks rendered list contract', () => {
    it('renders the standard Open control and export link in both responsive views', () => {
        render([track()]);

        expect(document.body.textContent).toContain('Cenote Traverse');
        expect(document.body.textContent).toContain('creator@example.com');
        expect(document.body.textContent).toContain('Read Only');
        expect(document.querySelectorAll('a[href$="/export/gpx/"]')).toHaveLength(2);
        expect(document.querySelectorAll('a[href$="111111111111/"]')).toHaveLength(2);
        expect(document.querySelectorAll('img[src$="right_arrow.svg"]')).toHaveLength(2);
        expect(document.querySelectorAll('.btn-edit-track')).toHaveLength(0);
        expect(document.querySelectorAll('.btn-delete-track')).toHaveLength(0);
    });

    it('keeps list actions identical for writers and administrators', () => {
        render([track({
            user_permission_level_label: 'READ_AND_WRITE',
            can_write: true,
        })]);

        expect(document.body.textContent).toContain('Read And Write');
        expect(document.querySelectorAll('img[src$="right_arrow.svg"]')).toHaveLength(2);
        expect(document.querySelectorAll('.btn-edit-track')).toHaveLength(0);
        expect(document.querySelectorAll('.btn-delete-track')).toHaveLength(0);

        render([track({
            user_permission_level_label: 'ADMIN',
            can_write: true,
            can_delete: true,
        })]);

        expect(document.body.textContent).toContain('Admin');
        expect(document.querySelectorAll('.btn-edit-track')).toHaveLength(0);
        expect(document.querySelectorAll('.btn-delete-track')).toHaveLength(0);
    });

    it('escapes API data, validates colors, and prevents attribute breakouts', () => {
        render([track({
            id: 'bad-id" onmouseover="alert(1)',
            name: '<img src=x onerror="alert(1)">',
            created_by: '<script>alert("creator")</script>',
            color: 'red; background-image:url(https://evil.test)',
            can_write: true,
        })]);

        expect(document.querySelectorAll('img')).toHaveLength(2);
        expect(document.querySelector<HTMLElement>('script')!).toBeNull();
        expect(document.querySelector<HTMLElement>('[onmouseover]')!).toBeNull();
        expect(document.querySelector<HTMLElement>('.w-3.h-3')!.style.backgroundColor)
            .toBe('rgb(148, 163, 184)');
        expect(document.body.textContent).toContain('<img src=x onerror="alert(1)">');
        expect(document.body.textContent).toContain('<script>alert("creator")</script>');
    });

    it('renders the responsive empty state', () => {
        render([]);

        expect(document.getElementById('tracks-table-body')!.textContent)
            .toContain('No GPS tracks yet');
        expect(document.getElementById('tracks-cards-container')!.textContent)
            .toContain('No GPS tracks yet');
        expect(document.querySelector<HTMLElement>('#tracks-table-body td')!.getAttribute('colspan'))
            .toBe('6');
    });
});

import { readFileSync } from 'node:fs';
import { init as initialize } from './gps-tracks.ts';
import { GPXImport } from '../../frontend_private/static/private/ts/gpx_import.ts';
import { attachTaggedEntityList } from '../../frontend_private/static/private/ts/forms/tagged_entity_list.ts';
vi.mock('../../frontend_private/static/private/ts/gpx_import.ts', () => ({ GPXImport: { init: vi.fn(), showModal: vi.fn(), clearFile: vi.fn(), hideModal: vi.fn(), upload: vi.fn(), hideWarningModal: vi.fn() } }));
vi.mock('../../frontend_private/static/private/ts/forms/tagged_entity_list.ts', () => ({ attachTaggedEntityList: vi.fn() }));
const jquery = readFileSync('frontend_public/static/ts/vendors/jquery-3.7.1.js', 'utf8');
beforeAll(() => { (0, eval)(jquery); });

describe('GPS Tracks initialization', () => {
    let listeners: [string, EventListenerOrEventListenerObject][];
    let reload: Mock<() => void>;
    beforeEach(() => {
        vi.clearAllMocks();
        listeners = [];
        const add = window.addEventListener.bind(window);
        vi.spyOn(window, 'addEventListener').mockImplementation((name, listener, options) => { listeners.push([name, listener]); add(name, listener, options); });
        reload = vi.fn();
        attachment.mockReturnValue({ reload, openEditModal: vi.fn(), openDeleteModal: vi.fn() });
        document.body.innerHTML = '<button id="import-gpx-button"></button><input id="gpx-file-input"><table><tbody id="tracks-table-body"></tbody></table><div id="tracks-cards-container"></div>';
    });
    afterEach(() => { for (const [name, listener] of listeners) window.removeEventListener(name, listener); $(document).off('click'); vi.restoreAllMocks(); });
    it('initializes imports before the list, renders both targets and reloads on the window event', () => {
        expect(init({ csrfToken: 'csrf', listEndpoint: '/tracks/', openIconUrl: '/open.svg' })).toBeUndefined();
        expect(GPXImport.init).toHaveBeenCalledWith('csrf');
        expect(vi.mocked(GPXImport.init).mock.invocationCallOrder[0]!).toBeLessThan(attachment.mock.invocationCallOrder[0]!);
        const options = attachment.mock.calls[0]![0];
        expect(options).toMatchObject({ listEndpoint: '/tracks/', entityLabel: 'GPS track', loadFailedMessage: 'Error loading GPS tracks' });
        options.renderList!([track()], {} as TaggedListApi);
        expect(document.querySelectorAll('img[src="/open.svg"]')).toHaveLength(2);
        window.dispatchEvent(new Event('speleo:refresh-gps-tracks'));
        expect(reload).toHaveBeenCalledTimes(1);
        $('#import-gpx-button').trigger('click');
        expect(GPXImport.showModal).toHaveBeenCalledTimes(1);
    });
    it('delegates actions with the clicked receiver, ignores unknown actions and repeats bindings', () => {
        init({}); init({});
        for (const action of ['clear', 'hide', 'upload', 'hide-warning', 'unknown']) {
            const button = document.createElement('button'); button.dataset.gpxAction = action; document.body.append(button); button.click();
        }
        expect(GPXImport.clearFile).toHaveBeenCalledTimes(2);
        expect(GPXImport.hideModal).toHaveBeenCalledTimes(2);
        expect(GPXImport.upload).toHaveBeenCalledTimes(2);
        expect(GPXImport.hideWarningModal).toHaveBeenCalledTimes(2);
        window.dispatchEvent(new Event('speleo:refresh-gps-tracks'));
        expect(reload).toHaveBeenCalledTimes(2);
    });
    it('preserves synchronous context and dependency failures', () => {
        expect(() => init()).toThrow(TypeError);
        const failure = new Error('import failed');
        vi.mocked(GPXImport.init).mockImplementationOnce(() => { throw failure; });
        expect(() => init({})).toThrow(failure);
        expect(attachTaggedEntityList).not.toHaveBeenCalled();
    });
});

function init(context?: unknown) { return initialize(context as GISUploadListContext); }
const attachment = vi.mocked(attachTaggedEntityList) as unknown as Mock<(options: TaggedListOptions<GISListRecord>) => TaggedListApi>;
