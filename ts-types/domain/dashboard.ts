/** Backend dashboard aggregates; calendar and project keys are data-defined. */
export type ContributionCalendar = Record<string, number>;
export type ProjectTypeCounts = Record<string, number>;
export interface MonthlyContributions {
    month: string;
    total: number;
    user: number;
}
export interface ContributionDataset {
    label: string;
    data: number[];
    borderColor: string;
    backgroundColor?: string;
    fill?: boolean;
    tension?: number;
    pointRadius?: number;
    pointHoverRadius?: number;
}
export interface CommitsChartConfig {
    type: 'line';
    options?: DashboardChartOptions;
    data: { labels: string[]; datasets: [ContributionDataset, ContributionDataset] };
}
export interface ProjectsChartConfig {
    type: 'doughnut';
    options?: DashboardChartOptions;
    data: { labels: string[]; datasets: [{ data: number[]; backgroundColor: string[]; borderColor?: string; borderWidth?: number }] };
    isEmpty: boolean;
    colors: string[];
}
export interface DashboardSummary {
    total_projects: number;
    total_teams: number;
    user_commits: number;
    total_stations_created: number;
    total_landmarks: number;
    total_gps_tracks: number;
}
export interface DashboardActivity {
    commit_id?: string | null;
    project_name: string;
    project_id: string;
    author_name: string;
    author_email: string;
    authored_date: string;
    message: string;
}

export interface DashboardChartOptions {
    responsive: boolean;
    maintainAspectRatio: boolean;
    interaction?: { mode: string; intersect: boolean };
    cutout?: string;
    plugins: { legend: { position?: string; labels: { color: string; usePointStyle: boolean; pointStyle: string; padding?: number } } };
    scales?: {
        x: { ticks: {color: string}; grid: {color: string} };
        y: { beginAtZero: boolean; ticks: {color: string; precision: number}; grid: {color: string} };
    };
}
export interface DashboardResponse {
    summary: DashboardSummary;
    commits_over_time: MonthlyContributions[];
    projects_by_type: ProjectTypeCounts;
    contribution_calendar: unknown;
    recent_activity: DashboardActivity[];
}
export interface HeatmapDay { date: Date; key: string; count: number; future: boolean }
export interface HeatmapMonth { label: string; startCol: number; colspan?: number }
