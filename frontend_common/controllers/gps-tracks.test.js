import { buildTrackListMarkup } from './gps-tracks.js';

function track(overrides = {}) {
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

function render(tracks) {
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
    };
});

afterEach(() => {
    document.body.innerHTML = '';
    delete globalThis.Urls;
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
        expect(document.querySelector('script')).toBeNull();
        expect(document.querySelector('[onmouseover]')).toBeNull();
        expect(document.querySelector('.w-3.h-3').style.backgroundColor)
            .toBe('rgb(148, 163, 184)');
        expect(document.body.textContent).toContain('<img src=x onerror="alert(1)">');
        expect(document.body.textContent).toContain('<script>alert("creator")</script>');
    });

    it('renders the responsive empty state', () => {
        render([]);

        expect(document.getElementById('tracks-table-body').textContent)
            .toContain('No GPS tracks yet');
        expect(document.getElementById('tracks-cards-container').textContent)
            .toContain('No GPS tracks yet');
        expect(document.querySelector('#tracks-table-body td').getAttribute('colspan'))
            .toBe('6');
    });
});
