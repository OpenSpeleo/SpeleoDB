import { createViewerUpdateScheduler } from '@speleodb/map-viewer/update-scheduler';
import { DEFAULTS } from './config.ts';

/** The web viewer owns one queue and its dynamically configured work budget. */
export const ViewerUpdates = createViewerUpdateScheduler({
    budget: () => DEFAULTS.VIEWER_WORK.BUDGET_MS,
});
