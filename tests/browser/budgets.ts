/** Shared limits for browser checks using software rendering on CI runners. */
export const BROWSER_TEST_BUDGETS = {
    testMs: 300_000,
    assertionMs: 60_000,
    viewerStartupMs: 180_000,
};
