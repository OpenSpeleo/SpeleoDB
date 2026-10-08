import type { DashboardChartConstructor } from '../../ts-types/browser/chart.d.ts';
import type { CommitsChartConfig, ProjectsChartConfig } from '../../ts-types/domain/dashboard.ts';
let Chart: Mock<(element: HTMLCanvasElement, config: CommitsChartConfig | ProjectsChartConfig) => void>;
import type { Mock } from 'vitest';
import type { ControllerAjaxCall } from '../../ts-types/testing/vitest/controller-ajax.ts';
let ajax: Mock<(options: ControllerAjaxCall) => {responseJSON?: unknown}>;
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init } from './dashboard.ts';
const jquery = readFileSync(resolve('frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
beforeAll(() => { (0, eval)(jquery); });
function response() {
    return { summary: { total_projects: 7, total_teams: 2, user_commits: 12, total_stations_created: 30, total_landmarks: 0, total_gps_tracks: 1 }, commits_over_time: [{ month: 'Jan', total: 12, user: 7 }], projects_by_type: { compass: 2 }, contribution_calendar: { '2026-01-01': 3 }, recent_activity: [] as unknown[] };
}
beforeEach(() => {
    ajax = vi.fn(() => ({}));
    vi.spyOn($, 'ajax').mockImplementation(ajax as unknown as JQueryStatic['ajax']);
    vi.stubGlobal('Urls', { 'api:v2:user-dashboard-stats': () => '/stats/', 'private:project_details': (id: string | number) => `/project/${id}/`, 'private:project_revision_explorer': (id: string | number, sha: string) => `/project/${id}/${sha}/` });
    Chart = vi.fn(function () {});
    window.Chart = Chart as unknown as DashboardChartConstructor;
    document.body.innerHTML = '<div id="stat-cards"><span class="stat-value" id="stat-projects"></span><span class="stat-value" id="stat-teams"></span><span class="stat-value" id="stat-commits"></span><span class="stat-value" id="stat-stations"></span><span class="stat-value" id="stat-landmarks"></span><span class="stat-value" id="stat-gps-tracks"></span></div><canvas id="commits-chart"></canvas><canvas id="projects-chart"></canvas><div id="projects-chart-empty" class="hidden"></div><table id="contribution-heatmap"></table><span id="heatmap-total-count"></span><div id="recent-activity"></div>';
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); delete (window as unknown as {Chart?: unknown}).Chart; document.body.innerHTML = ''; });
it('fetches immediately and renders the real stat, chart and 53-week heatmap implementations', () => {
    expect(init()).toBeUndefined();
    expect(ajax.mock.calls[0]![0]).toMatchObject({ url: '/stats/', type: 'GET', dataType: 'json' });
    ajax.mock.calls[0]![0].success(response());
    expect($('#stat-cards .stat-value').map(function () { return $(this).text(); }).get()).toEqual(['7', '2', '12', '30', '0', '1']);
    expect(Chart).toHaveBeenCalledTimes(2);
    expect(Chart.mock.calls[0]![1]).toMatchObject({ type: 'line', data: { labels: ['Jan'], datasets: [{ data: [12], fill: true }, { data: [7], fill: true }] } });
    expect(Chart.mock.calls[1]![1]).toMatchObject({ type: 'doughnut', data: { labels: ['Compass'] } });
    expect($('#contribution-heatmap tbody tr').length).toBe(7);
    expect($('#contribution-heatmap tbody tr').first().find('td').length).toBe(54);
    expect($('#heatmap-total-count').text()).toBe('3');
    expect($('#recent-activity').text()).toContain('No recent activity');
});
it('escapes activity fields, filters system commits and constructs project and revision links', () => {
    init();
    const data = response();
    data.recent_activity = [{ author_name: 'SpeleoDB', message: '[Automated] hidden' }, { author_name: '<Diver>', project_name: '<Cave>', message: '<message>', project_id: 1, commit_id: '1234567890', authored_date: '2026-01-01T12:00:00Z' }];
    ajax.mock.calls[0]![0].success(data);
    expect($('.activity-row').length).toBe(1);
    expect($('.activity-msg').text()).toBe('<message>');
    expect($('.activity-badge-project').text()).toBe('<Cave>');
    expect($('.activity-badge-project').attr('href')).toBe('/project/1/');
    expect($('.activity-badge-sha').text()).toBe('1234567');
    expect($('#recent-activity message, #recent-activity Cave').length).toBe(0);
});
it('renders empty project chart state and request errors', () => {
    init();
    ajax.mock.calls[0]![0].success({ ...response(), projects_by_type: {} });
    expect(Chart).toHaveBeenCalledOnce();
    expect($('#projects-chart')[0]!.style.display).toBe('none');
    expect($('#projects-chart-empty').hasClass('hidden')).toBe(false);
    ajax.mock.calls[0]![0].error();
    expect($('#stat-cards .stat-value').map(function () { return $(this).text(); }).get()).toEqual(['-', '-', '-', '-', '-', '-']);
    expect($('#recent-activity').text()).toBe('Failed to load activity');
});
it('reissues requests on repeated initialization and skips missing chart or display DOM', () => {
    document.body.innerHTML = '';
    delete (window as unknown as {Chart?: unknown}).Chart;
    init();
    init();
    expect(ajax).toHaveBeenCalledTimes(2);
    expect(() => ajax.mock.calls[1]![0].success(response())).not.toThrow();
});
it('lets malformed response and missing required chart global fail at their actual callback boundary', () => {
    init();
    expect(() => ajax.mock.calls[0]![0].success({})).toThrow(TypeError);
    delete (window as unknown as {Chart?: unknown}).Chart;
    expect(() => ajax.mock.calls[0]![0].success(response())).toThrow(TypeError);
});
