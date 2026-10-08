import type { CommitsChartConfig, ProjectsChartConfig } from '../domain/dashboard.ts';
export interface DashboardChartConstructor {
    new(element: HTMLCanvasElement, config: CommitsChartConfig | ProjectsChartConfig): object;
}
declare global { interface Window { Chart: DashboardChartConstructor } }
