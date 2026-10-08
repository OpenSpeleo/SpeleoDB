/** Shared limits for browser checks using software rendering on CI runners. */
export const BROWSER_TEST_BUDGETS = {
    testMs: 300_000,
    assertionMs: 60_000,
    viewerStartupMs: 180_000,
    // The recorded CI stress case needed 10,028 ms between feedback frames.
    // These are regression limits for this runner, not UI responsiveness targets.
    feedbackFrameMs: 15_000,
    preparationGapMs: 250,
};
