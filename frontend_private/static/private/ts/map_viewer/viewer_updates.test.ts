import { DEFAULTS } from './config.ts';
import { ViewerUpdates } from './viewer_updates.ts';

afterEach(async () => {
    ViewerUpdates.cancelAll();
    await ViewerUpdates.whenIdle();
});

it('shares the web queue across consumers and releases pending display work on teardown', async () => {
    const otherConsumer = await import('./viewer_updates.ts');
    expect(otherConsumer.ViewerUpdates).toBe(ViewerUpdates);
    let applied = false;
    const pending = ViewerUpdates.schedule('display', () => { applied = true; });
    otherConsumer.ViewerUpdates.cancelAll();
    expect(await pending).toEqual({ status: 'cancelled' });
    await ViewerUpdates.whenIdle();
    expect(applied).toBe(false);
});

it('reads the current web work budget through the singleton adapter', async () => {
    const originalBudget = DEFAULTS.VIEWER_WORK.BUDGET_MS;
    try {
        const result = await ViewerUpdates.schedule('budget-policy', async context => {
            DEFAULTS.VIEWER_WORK.BUDGET_MS = 0;
            expect(context.shouldYield()).toBe(true);
            DEFAULTS.VIEWER_WORK.BUDGET_MS = Infinity;
            expect(context.shouldYield()).toBe(false);
            expect(await context.yield()).toBe(true);
        });
        expect(result).toEqual({ status: 'applied' });
    } finally {
        DEFAULTS.VIEWER_WORK.BUDGET_MS = originalBudget;
    }
});
