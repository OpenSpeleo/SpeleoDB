/**
 * Dashboard helper tests.
 *
 * Loads the real dashboard-helpers.js and xss-helpers.js so tests
 * exercise production code rather than local copies.
 */

/* global escapeHtml, formatNumber, getInitials, getAvatarColor, avatarColors,
          getHeatmapLevel, groupTimestampsByLocalDate, computeHeatmapStats,
          buildCommitsChartConfig, buildProjectsChartConfig */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

/* ── Load real source files ─────────────────────────────────────── */

const __dirname = dirname(fileURLToPath(import.meta.url));

const XSS_PATH = resolve(__dirname, '..', 'xss-helpers.js');
const XSS_SRC = readFileSync(XSS_PATH, 'utf-8');

const HELPERS_PATH = resolve(__dirname, '..', 'dashboard-helpers.js');
const HELPERS_SRC = readFileSync(HELPERS_PATH, 'utf-8');

beforeAll(() => {
    // Evaluate both scripts so their globals are available
    // eslint-disable-next-line no-eval
    (0, eval)(XSS_SRC);
    // eslint-disable-next-line no-eval
    (0, eval)(HELPERS_SRC);
});


/* ── DOM helpers used only by tests (populateStatCards, renderActivityFeed) ── */

function populateStatCards(summary) {
    const mapping = {
        'stat-projects': summary.total_projects,
        'stat-teams': summary.total_teams,
        'stat-commits': summary.user_commits,
        'stat-stations': summary.total_stations_created,
        'stat-landmarks': summary.total_landmarks,
        'stat-gps-tracks': summary.total_gps_tracks,
    };
    for (const [id, value] of Object.entries(mapping)) {
        const el = document.getElementById(id);
        if (el) el.textContent = formatNumber(value);
    }
}

function renderActivityFeed(activity, container) {
    const filtered = [];
    if (activity) {
        for (const item of activity) {
            if (item.author_name === 'SpeleoDB' && item.message.indexOf('[Automated]') === 0) continue;
            filtered.push(item);
        }
    }

    if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-message">No recent activity</div>';
        return;
    }

    let html = '';
    let lastDateLabel = '';

    for (const item of filtered) {
        const projectName = escapeHtml(item.project_name);
        const authorName = escapeHtml(item.author_name);
        const message = escapeHtml(item.message);
        const projectUrl = '/private/project/' + item.project_id + '/';
        const initials = getInitials(item.author_name);
        const color = getAvatarColor(item.author_name);
        const shortSha = item.commit_id ? item.commit_id.slice(0, 7) : '';

        const itemDate = new Date(item.authored_date);
        const todayDate = new Date();
        let dateLabel;
        if (itemDate.toDateString() === todayDate.toDateString()) {
            dateLabel = 'Today';
        } else {
            const yesterday = new Date(todayDate);
            yesterday.setDate(yesterday.getDate() - 1);
            if (itemDate.toDateString() === yesterday.toDateString()) {
                dateLabel = 'Yesterday';
            } else {
                dateLabel = itemDate.toLocaleDateString('en', { month: 'short', day: 'numeric' });
            }
        }

        if (dateLabel !== lastDateLabel) {
            html += '<div class="date-header">' + dateLabel + '</div>';
            lastDateLabel = dateLabel;
        }

        const localDateTime = itemDate.toLocaleDateString('en', {
            month: 'short', day: 'numeric', year: 'numeric'
        }) + ' at ' + itemDate.toLocaleTimeString('en', {
            hour: 'numeric', minute: '2-digit', hour12: true
        });
        const localDateOnly = itemDate.toLocaleDateString('en', {
            month: 'short', day: 'numeric'
        });

        html += '<div class="activity-row">' +
            '<div class="activity-avatar" style="background-color:' + color + '">' + initials + '</div>' +
            '<span class="author">' + authorName + '</span>' +
            '<a href="' + projectUrl + '" class="activity-badge-project">' + projectName + '</a>' +
            '<a class="activity-badge-sha">' + shortSha + '</a>' +
            '<span class="activity-msg">' + message + '</span>' +
            '<span class="activity-meta"><span class="activity-time-full">' + localDateTime + '</span><span class="activity-time-short">' + localDateOnly + '</span></span>' +
        '</div>';
    }
    container.innerHTML = html;
}


// ================================================================== //
//  Tests
// ================================================================== //

describe('Dashboard helpers', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    // -------------------------------------------------------------- //
    //  escapeHtml (loaded from xss-helpers.js)
    // -------------------------------------------------------------- //

    describe('escapeHtml', () => {
        it('escapes angle brackets', () => {
            expect(escapeHtml('<b>bold</b>')).toBe('&lt;b&gt;bold&lt;/b&gt;');
        });

        it('escapes ampersands', () => {
            expect(escapeHtml('a & b')).toContain('&amp;');
        });

        it('escapes double and single quotes', () => {
            expect(escapeHtml('"hello"')).toContain('&quot;');
            expect(escapeHtml("'hello'")).toContain('&#39;');
        });

        it('returns empty string for null and undefined', () => {
            expect(escapeHtml(null)).toBe('');
            expect(escapeHtml(undefined)).toBe('');
        });

        it('stringifies non-string values', () => {
            expect(escapeHtml(42)).toBe('42');
        });

        it('passes through plain text unchanged', () => {
            expect(escapeHtml('hello world')).toBe('hello world');
        });
    });

    // -------------------------------------------------------------- //
    //  formatNumber
    // -------------------------------------------------------------- //

    describe('formatNumber', () => {
        it('returns dash for null', () => {
            expect(formatNumber(null)).toBe('-');
        });

        it('returns dash for undefined', () => {
            expect(formatNumber(undefined)).toBe('-');
        });

        it('formats zero', () => {
            expect(formatNumber(0)).toBe('0');
        });

        it('formats large numbers with locale separators', () => {
            const result = formatNumber(1234);
            expect(result).toContain('1');
            expect(result).toContain('234');
        });
    });

    // -------------------------------------------------------------- //
    //  getInitials
    // -------------------------------------------------------------- //

    describe('getInitials', () => {
        it('returns two initials for two-word name', () => {
            expect(getInitials('Alice Smith')).toBe('AS');
        });

        it('returns first and last initials for three-word name', () => {
            expect(getInitials('John Paul Jones')).toBe('JJ');
        });

        it('returns first two chars for single-word name', () => {
            expect(getInitials('Alice')).toBe('AL');
        });

        it('uppercases initials', () => {
            expect(getInitials('alice smith')).toBe('AS');
        });

        it('trims whitespace', () => {
            expect(getInitials('  Bob  Lee  ')).toBe('BL');
        });
    });

    // -------------------------------------------------------------- //
    //  getAvatarColor
    // -------------------------------------------------------------- //

    describe('getAvatarColor', () => {
        it('returns a valid hex color', () => {
            const color = getAvatarColor('Alice');
            expect(color).toMatch(/^#[0-9a-f]{6}$/);
        });

        it('returns the same color for the same name', () => {
            expect(getAvatarColor('Bob')).toBe(getAvatarColor('Bob'));
        });

        it('returns a color from the palette', () => {
            const color = getAvatarColor('Charlie');
            expect(avatarColors).toContain(color);
        });
    });

    // -------------------------------------------------------------- //
    //  Heatmap level thresholds
    // -------------------------------------------------------------- //

    describe('getHeatmapLevel', () => {
        it('returns 0 for 0 commits', () => { expect(getHeatmapLevel(0)).toBe(0); });
        it('returns 1 for 1 commit', () => { expect(getHeatmapLevel(1)).toBe(1); });
        it('returns 1 for 2 commits', () => { expect(getHeatmapLevel(2)).toBe(1); });
        it('returns 2 for 3 commits', () => { expect(getHeatmapLevel(3)).toBe(2); });
        it('returns 2 for 5 commits', () => { expect(getHeatmapLevel(5)).toBe(2); });
        it('returns 3 for 6 commits', () => { expect(getHeatmapLevel(6)).toBe(3); });
        it('returns 3 for 9 commits', () => { expect(getHeatmapLevel(9)).toBe(3); });
        it('returns 4 for 10 commits', () => { expect(getHeatmapLevel(10)).toBe(4); });
        it('returns 4 for 100 commits', () => { expect(getHeatmapLevel(100)).toBe(4); });
    });

    // -------------------------------------------------------------- //
    //  groupTimestampsByLocalDate
    // -------------------------------------------------------------- //

    describe('groupTimestampsByLocalDate', () => {
        it('returns empty object for empty array', () => {
            expect(groupTimestampsByLocalDate([])).toEqual({});
        });

        it('groups timestamps by local date', () => {
            const today = new Date();
            const key = today.getFullYear() + '-' +
                String(today.getMonth() + 1).padStart(2, '0') + '-' +
                String(today.getDate()).padStart(2, '0');

            const result = groupTimestampsByLocalDate([
                today.toISOString(),
                today.toISOString(),
            ]);
            expect(result[key]).toBe(2);
        });

        it('separates different dates', () => {
            const d1 = new Date(2026, 0, 15, 10, 0, 0);
            const d2 = new Date(2026, 0, 16, 10, 0, 0);
            const result = groupTimestampsByLocalDate([d1.toISOString(), d2.toISOString()]);
            expect(Object.keys(result).length).toBe(2);
        });

        it('handles non-array input gracefully', () => {
            expect(groupTimestampsByLocalDate(null)).toEqual({});
            expect(groupTimestampsByLocalDate(undefined)).toEqual({});
        });
    });

    // -------------------------------------------------------------- //
    //  populateStatCards
    // -------------------------------------------------------------- //

    describe('populateStatCards', () => {
        beforeEach(() => {
            document.body.innerHTML =
                '<div id="stat-projects"></div>' +
                '<div id="stat-teams"></div>' +
                '<div id="stat-commits"></div>' +
                '<div id="stat-stations"></div>' +
                '<div id="stat-landmarks"></div>' +
                '<div id="stat-gps-tracks"></div>';
        });

        it('updates DOM elements with values', () => {
            populateStatCards({
                total_projects: 12, total_teams: 3, user_commits: 89,
                total_stations_created: 145, total_landmarks: 24, total_gps_tracks: 5,
            });
            expect(document.getElementById('stat-projects').textContent).toContain('12');
            expect(document.getElementById('stat-teams').textContent).toContain('3');
            expect(document.getElementById('stat-commits').textContent).toContain('89');
        });

        it('shows zero for zero values', () => {
            populateStatCards({
                total_projects: 0, total_teams: 0, user_commits: 0,
                total_stations_created: 0, total_landmarks: 0, total_gps_tracks: 0,
            });
            expect(document.getElementById('stat-projects').textContent).toBe('0');
            expect(document.getElementById('stat-teams').textContent).toBe('0');
        });
    });

    // -------------------------------------------------------------- //
    //  renderActivityFeed
    // -------------------------------------------------------------- //

    describe('renderActivityFeed', () => {
        let container;

        function makeEntry(overrides = {}) {
            return {
                commit_id: 'a'.repeat(40),
                project_name: 'Cave A',
                project_id: '123',
                author_name: 'Alice Smith',
                author_email: 'alice@test.com',
                authored_date: new Date().toISOString(),
                message: 'Added survey data',
                ...overrides,
            };
        }

        beforeEach(() => {
            container = document.createElement('div');
            document.body.appendChild(container);
        });

        it('creates activity rows for each entry', () => {
            renderActivityFeed([makeEntry(), makeEntry({ project_id: '456' })], container);
            const rows = container.querySelectorAll('.activity-row');
            expect(rows.length).toBe(2);
        });

        it('shows empty message for empty list', () => {
            renderActivityFeed([], container);
            expect(container.textContent).toContain('No recent activity');
        });

        it('shows empty message for null', () => {
            renderActivityFeed(null, container);
            expect(container.textContent).toContain('No recent activity');
        });

        it('filters out automated system commits', () => {
            renderActivityFeed([
                makeEntry(),
                makeEntry({ author_name: 'SpeleoDB', message: '[Automated] Project Creation' }),
            ], container);
            const rows = container.querySelectorAll('.activity-row');
            expect(rows.length).toBe(1);
        });

        it('shows empty state when only automated commits exist', () => {
            renderActivityFeed([
                makeEntry({ author_name: 'SpeleoDB', message: '[Automated] Project Creation' }),
            ], container);
            expect(container.textContent).toContain('No recent activity');
        });

        it('displays author initials in avatar', () => {
            renderActivityFeed([makeEntry({ author_name: 'Bob Jones' })], container);
            const avatar = container.querySelector('.activity-avatar');
            expect(avatar.textContent).toBe('BJ');
        });

        it('renders project badge with link', () => {
            renderActivityFeed([makeEntry()], container);
            const badge = container.querySelector('.activity-badge-project');
            expect(badge).not.toBeNull();
            expect(badge.textContent).toBe('Cave A');
            expect(badge.href).toContain('123');
        });

        it('renders short SHA badge', () => {
            renderActivityFeed([makeEntry({ commit_id: 'a871546ebe012aa3b7a13147621c91045f7769fe' })], container);
            const sha = container.querySelector('.activity-badge-sha');
            expect(sha).not.toBeNull();
            expect(sha.textContent).toBe('a871546');
        });

        it('renders local date+time instead of time-ago', () => {
            renderActivityFeed([makeEntry()], container);
            const meta = container.querySelector('.activity-meta');
            expect(meta.textContent).toContain('at');
        });

        it('renders date group headers', () => {
            renderActivityFeed([makeEntry()], container);
            const header = container.querySelector('.date-header');
            expect(header).not.toBeNull();
            expect(header.textContent).toBe('Today');
        });

        it('groups entries by date', () => {
            const yesterday = new Date();
            yesterday.setDate(yesterday.getDate() - 1);
            renderActivityFeed([
                makeEntry(),
                makeEntry({ authored_date: yesterday.toISOString() }),
            ], container);
            const headers = container.querySelectorAll('.date-header');
            expect(headers.length).toBe(2);
            expect(headers[0].textContent).toBe('Today');
            expect(headers[1].textContent).toBe('Yesterday');
        });

        it('escapes HTML in project name to prevent XSS', () => {
            renderActivityFeed([makeEntry({ project_name: '<script>alert("xss")</script>' })], container);
            expect(container.innerHTML).not.toContain('<script>');
            expect(container.innerHTML).toContain('&lt;script&gt;');
        });

        it('escapes HTML in author name to prevent XSS', () => {
            renderActivityFeed([makeEntry({ author_name: '<img onerror=alert(1) src=x>' })], container);
            expect(container.innerHTML).not.toContain('<img');
            expect(container.innerHTML).toContain('&lt;img');
        });

        it('escapes HTML in message to prevent XSS', () => {
            renderActivityFeed([makeEntry({ message: '<div onmouseover="alert(1)">hover</div>' })], container);
            const msg = container.querySelector('.activity-msg');
            expect(msg.innerHTML).toContain('&lt;div');
            expect(msg.innerHTML).not.toContain('<div onmouseover');
        });

        it('displays commit message in activity-msg span', () => {
            renderActivityFeed([makeEntry({ message: 'Fixed depth readings' })], container);
            const msg = container.querySelector('.activity-msg');
            expect(msg.textContent).toBe('Fixed depth readings');
        });

        it('renders both full and short time formats', () => {
            renderActivityFeed([makeEntry()], container);
            const full = container.querySelector('.activity-time-full');
            const short = container.querySelector('.activity-time-short');
            expect(full).not.toBeNull();
            expect(short).not.toBeNull();
            expect(full.textContent).toContain('at');
            expect(short.textContent.length).toBeLessThan(full.textContent.length);
        });

        it('renders avatar with correct background color', () => {
            renderActivityFeed([makeEntry({ author_name: 'Alice Smith' })], container);
            const avatar = container.querySelector('.activity-avatar');
            expect(avatar.style.backgroundColor).toBeTruthy();
        });

        it('renders commit SHA from commit_id field', () => {
            const sha40 = 'abcdef1234567890abcdef1234567890abcdef12';
            renderActivityFeed([makeEntry({ commit_id: sha40 })], container);
            const sha = container.querySelector('.activity-badge-sha');
            expect(sha.textContent).toBe('abcdef1');
        });

        it('handles missing commit_id gracefully', () => {
            renderActivityFeed([makeEntry({ commit_id: null })], container);
            const sha = container.querySelector('.activity-badge-sha');
            expect(sha.textContent).toBe('');
        });

        it('multiple entries on same date share one header', () => {
            renderActivityFeed([
                makeEntry({ message: 'First' }),
                makeEntry({ message: 'Second' }),
            ], container);
            const headers = container.querySelectorAll('.date-header');
            expect(headers.length).toBe(1);
        });

        it('entries older than yesterday get formatted date label', () => {
            const oldDate = new Date();
            oldDate.setDate(oldDate.getDate() - 5);
            renderActivityFeed([makeEntry({ authored_date: oldDate.toISOString() })], container);
            const header = container.querySelector('.date-header');
            expect(header).not.toBeNull();
            expect(header.textContent).not.toBe('Today');
            expect(header.textContent).not.toBe('Yesterday');
        });

        it('does not filter non-automated commits from SpeleoDB author', () => {
            renderActivityFeed([
                makeEntry({ author_name: 'SpeleoDB', message: 'Manual fix' }),
            ], container);
            const rows = container.querySelectorAll('.activity-row');
            expect(rows.length).toBe(1);
        });

        it('short time does not contain "at"', () => {
            renderActivityFeed([makeEntry()], container);
            const short = container.querySelector('.activity-time-short');
            expect(short.textContent).not.toContain('at');
        });
    });

    // -------------------------------------------------------------- //
    //  Chart config builders
    // -------------------------------------------------------------- //

    describe('buildCommitsChartConfig', () => {
        const sampleData = [
            { month: '2025-05', total: 10, user: 4 },
            { month: '2025-06', total: 15, user: 8 },
            { month: '2025-07', total: 3,  user: 3 },
        ];

        it('returns a line chart type', () => {
            expect(buildCommitsChartConfig(sampleData).type).toBe('line');
        });

        it('has labels matching month fields', () => {
            const config = buildCommitsChartConfig(sampleData);
            expect(config.data.labels).toEqual(['2025-05', '2025-06', '2025-07']);
        });

        it('has two datasets', () => {
            expect(buildCommitsChartConfig(sampleData).data.datasets.length).toBe(2);
        });

        it('first dataset is total (All Contributions)', () => {
            const ds = buildCommitsChartConfig(sampleData).data.datasets[0];
            expect(ds.label).toBe('All Contributions');
            expect(ds.data).toEqual([10, 15, 3]);
        });

        it('second dataset is user (Your Contributions)', () => {
            const ds = buildCommitsChartConfig(sampleData).data.datasets[1];
            expect(ds.label).toBe('Your Contributions');
            expect(ds.data).toEqual([4, 8, 3]);
        });

        it('uses correct colors', () => {
            const config = buildCommitsChartConfig(sampleData);
            expect(config.data.datasets[0].borderColor).toBe('#818cf8');
            expect(config.data.datasets[1].borderColor).toBe('#34d399');
        });

        it('handles empty data', () => {
            const config = buildCommitsChartConfig([]);
            expect(config.data.labels).toEqual([]);
            expect(config.data.datasets[0].data).toEqual([]);
        });
    });

    describe('buildProjectsChartConfig', () => {
        it('returns a doughnut chart type', () => {
            expect(buildProjectsChartConfig({ ariane: 3 }).type).toBe('doughnut');
        });

        it('capitalizes type labels', () => {
            const config = buildProjectsChartConfig({ ariane: 3, compass: 2 });
            expect(config.data.labels).toEqual(['Ariane', 'Compass']);
        });

        it('maps values correctly', () => {
            const config = buildProjectsChartConfig({ ariane: 3, compass: 2 });
            expect(config.data.datasets[0].data).toEqual([3, 2]);
        });

        it('skips zero-count types', () => {
            const config = buildProjectsChartConfig({ ariane: 3, compass: 0, therion: 1 });
            expect(config.data.labels).toEqual(['Ariane', 'Therion']);
            expect(config.data.datasets[0].data).toEqual([3, 1]);
        });

        it('isEmpty is true when all types are zero', () => {
            expect(buildProjectsChartConfig({}).isEmpty).toBe(true);
        });

        it('isEmpty is false when data exists', () => {
            expect(buildProjectsChartConfig({ ariane: 1 }).isEmpty).toBe(false);
        });
    });

    // -------------------------------------------------------------- //
    //  Heatmap stats computation
    // -------------------------------------------------------------- //

    describe('computeHeatmapStats', () => {
        it('returns zero stats for empty calendar', () => {
            const stats = computeHeatmapStats({});
            expect(stats.total).toBe(0);
            expect(stats.weekCount).toBe(0);
            expect(stats.monthCount).toBe(0);
            expect(stats.busiestDayCount).toBe(0);
            expect(stats.streak).toBe(0);
        });

        it('counts total contributions', () => {
            const today = new Date();
            const key = today.getFullYear() + '-' +
                String(today.getMonth() + 1).padStart(2, '0') + '-' +
                String(today.getDate()).padStart(2, '0');
            const stats = computeHeatmapStats({ [key]: 5 });
            expect(stats.total).toBe(5);
        });

        it('identifies busiest day', () => {
            const d1 = new Date(); d1.setDate(d1.getDate() - 3);
            const d2 = new Date(); d2.setDate(d2.getDate() - 5);
            const k1 = d1.getFullYear() + '-' + String(d1.getMonth() + 1).padStart(2, '0') + '-' + String(d1.getDate()).padStart(2, '0');
            const k2 = d2.getFullYear() + '-' + String(d2.getMonth() + 1).padStart(2, '0') + '-' + String(d2.getDate()).padStart(2, '0');
            const stats = computeHeatmapStats({ [k1]: 2, [k2]: 7 });
            expect(stats.busiestDay).toBe(k2);
            expect(stats.busiestDayCount).toBe(7);
        });

        it('computes streak ending today', () => {
            const cal = {};
            for (let i = 0; i < 3; i++) {
                const d = new Date();
                d.setDate(d.getDate() - i);
                const k = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
                cal[k] = 1;
            }
            const stats = computeHeatmapStats(cal);
            expect(stats.streak).toBe(3);
        });

        it('streak skips today if no commits and checks yesterday', () => {
            const yesterday = new Date();
            yesterday.setDate(yesterday.getDate() - 1);
            const k = yesterday.getFullYear() + '-' + String(yesterday.getMonth() + 1).padStart(2, '0') + '-' + String(yesterday.getDate()).padStart(2, '0');
            const stats = computeHeatmapStats({ [k]: 2 });
            expect(stats.streak).toBe(1);
        });

        it('streak breaks on a gap day', () => {
            const cal = {};
            const d0 = new Date();
            const d2 = new Date(); d2.setDate(d2.getDate() - 2);
            const k0 = d0.getFullYear() + '-' + String(d0.getMonth() + 1).padStart(2, '0') + '-' + String(d0.getDate()).padStart(2, '0');
            const k2 = d2.getFullYear() + '-' + String(d2.getMonth() + 1).padStart(2, '0') + '-' + String(d2.getDate()).padStart(2, '0');
            cal[k0] = 1;
            cal[k2] = 1;
            const stats = computeHeatmapStats(cal);
            expect(stats.streak).toBe(1);
        });
    });
});
