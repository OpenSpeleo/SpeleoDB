import type { GISListRecord, GISUploadErrorDetails } from '../../ts-types/controllers/gis-lists.ts';
import type { ApplicationUrls } from '../../ts-types/browser/urls.d.ts';
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

import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });
import { init } from './gps-tracks.ts';

it('loads tracks through the generated client and reloads after import notification', async () => {
    document.body.innerHTML = '<button id="import-gpx-button"></button><input id="gpx-file-input" type="file"><table><tbody id="tracks-table-body"></tbody></table><div id="tracks-cards-container"></div>';
    server.reply({ json: [track()] });
    const listeners = vi.spyOn(window, 'addEventListener');
    try {
        init({ openIconUrl: '/open.svg' });
        await vi.waitFor(() => expect(document.querySelectorAll('img[src="/open.svg"]')).toHaveLength(2));
        expect(server.requests[0]!.path).toBe('/api/v2/gps_tracks/');
        server.reply({ json: [] }); window.dispatchEvent(new Event('speleo:refresh-gps-tracks'));
        await vi.waitFor(() => expect($('#tracks-table-body').text()).toContain('No GPS tracks yet'));
        expect(server.requests).toHaveLength(2);
    } finally {
        for (const [name, listener, options] of listeners.mock.calls) window.removeEventListener(name, listener, options);
        listeners.mockRestore(); $(document).off();
    }
});
