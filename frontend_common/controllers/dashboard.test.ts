import type { DashboardChartConstructor } from '../../ts-types/browser/chart.d.ts';
import type { CommitsChartConfig, ProjectsChartConfig } from '../../ts-types/domain/dashboard.ts';
import type { Mock } from 'vitest';
import { init } from './dashboard.ts';
let Chart: Mock<(element: HTMLCanvasElement, config: CommitsChartConfig | ProjectsChartConfig) => void>;
import { loadJQuery, setBrowserUrl, startApiServer } from '../test/api-server.ts';
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; loadJQuery(); server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/private/fixture/`); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });
function response() {
    return { summary: { total_projects: 7, total_teams: 2, user_commits: 12, total_stations_created: 30, total_landmarks: 0, total_gps_tracks: 1 }, commits_over_time: [{ month: 'Jan', total: 12, user: 7 }], projects_by_type: { compass: 2 }, contribution_calendar: { '2026-01-01': 3 }, recent_activity: [] as unknown[] };
}
beforeEach(() => {
    server.reply({ json: response() });
    vi.stubGlobal('Urls', { 'api:v2:user-dashboard-stats': () => '/stats/', 'private:project_details': (id: string | number) => `/project/${id}/`, 'private:project_revision_explorer': (id: string | number, sha: string) => `/project/${id}/${sha}/` });
    // JSDOM has no canvas renderer; only the third-party chart renderer is isolated.
    Chart = vi.fn(function () {});
    window.Chart = Chart as unknown as DashboardChartConstructor;
    document.body.innerHTML = '<div id="stat-cards"><span class="stat-value" id="stat-projects"></span><span class="stat-value" id="stat-teams"></span><span class="stat-value" id="stat-commits"></span><span class="stat-value" id="stat-stations"></span><span class="stat-value" id="stat-landmarks"></span><span class="stat-value" id="stat-gps-tracks"></span></div><canvas id="commits-chart"></canvas><canvas id="projects-chart"></canvas><div id="projects-chart-empty" class="hidden"></div><table id="contribution-heatmap"></table><span id="heatmap-total-count"></span><div id="recent-activity"></div>';
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); delete (window as unknown as {Chart?: unknown}).Chart; document.body.innerHTML = ''; });
it('fetches immediately and renders the real stat, chart and 53-week heatmap implementations', async () => {
    expect(init()).toBeUndefined();
    await vi.waitFor(() => expect($('#stat-projects').text()).toBe('7'));
    expect(server.requests[0]).toMatchObject({ method: 'GET', path: '/api/v2/user/dashboard-stats/' });
    expect($('#stat-cards .stat-value').map(function () { return $(this).text(); }).get()).toEqual(['7', '2', '12', '30', '0', '1']);
    expect(Chart).toHaveBeenCalledTimes(2);
    expect(Chart.mock.calls[0]![1]).toMatchObject({ type: 'line', data: { labels: ['Jan'], datasets: [{ data: [12], fill: true }, { data: [7], fill: true }] } });
    expect(Chart.mock.calls[1]![1]).toMatchObject({ type: 'doughnut', data: { labels: ['Compass'] } });
    expect($('#contribution-heatmap tbody tr').length).toBe(7);
    expect($('#contribution-heatmap tbody tr').first().find('td').length).toBe(54);
    expect($('#heatmap-total-count').text()).toBe('3');
    expect($('#recent-activity').text()).toContain('No recent activity');
});
it('escapes activity fields, filters system commits and constructs project and revision links', async () => {
    const data = response();
    data.recent_activity = [{ author_name: 'SpeleoDB', message: '[Automated] hidden' }, { author_name: '<Diver>', project_name: '<Cave>', message: '<message>', project_id: 1, commit_id: '1234567890', authored_date: '2026-01-01T12:00:00Z' }];
    server.reply({ json: data }); init();
    await vi.waitFor(() => expect($('.activity-row')).toHaveLength(1));
    expect($('.activity-row').length).toBe(1);
    expect($('.activity-msg').text()).toBe('<message>');
    expect($('.activity-badge-project').text()).toBe('<Cave>');
    expect($('.activity-badge-project').attr('href')).toBe('/project/1/');
    expect($('.activity-badge-sha').text()).toBe('1234567');
    expect($('#recent-activity message, #recent-activity Cave').length).toBe(0);
});
it('renders an empty project chart and the HTTP error state', async () => {
    server.reply({ json: { ...response(), projects_by_type: {} } }); init();
    await vi.waitFor(() => expect($('#stat-projects').text()).toBe('7'));
    expect(Chart).toHaveBeenCalledOnce();
    expect($('#projects-chart')[0]!.style.display).toBe('none');
    expect($('#projects-chart-empty').hasClass('hidden')).toBe(false);
    server.reply({ status: 403, json: { detail: 'Denied' } }); init();
    await vi.waitFor(() => expect($('#recent-activity').text()).toBe('Failed to load activity'));
    expect($('#stat-cards .stat-value').map(function () { return $(this).text(); }).get()).toEqual(['-', '-', '-', '-', '-', '-']);
});
