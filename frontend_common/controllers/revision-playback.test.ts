import type { ProjectRevisionMapContext } from '../../ts-types/controllers/project-revision-map.ts';
import type { ProjectMapInput } from '../../ts-types/domain/map-config.ts';
import { initRevisionPlayback } from './revision-playback.ts';
import type { RevisionPlaybackViewer } from './revision-playback.ts';
import { setBrowserUrl, startApiServer } from '../test/api-server.ts';

let server: Awaited<ReturnType<typeof startApiServer>>;
let stopPlayback: (() => void) | undefined;
const initialSha = 'a'.repeat(40);
const nextSha = 'b'.repeat(40);
const survey = { type: 'FeatureCollection', features: [] };

function context(): ProjectRevisionMapContext {
    const value = {
        mapboxToken: '', commitSha: initialSha, artifactRevision: 'original',
        project: { id: 'survey', name: 'Survey', color: '#22c55e', geojson_file: `${server.origin}/first.geojson` },
        revisions: [
            { commitSha: nextSha, artifactRevision: 'next', available: true, url: `/revisions/${nextSha}/`, geojsonUrl: `${server.origin}/next.geojson`, dateLabel: 'May 15, 2024', displayDateLabel: 'May 15, 2024 14:32', timestampLabel: 'May 15, 2024 at 14:32 UTC', message: '<Eastern passage>', authorName: '<Alex>' },
            { commitSha: initialSha, artifactRevision: 'original', available: true, url: `/revisions/${initialSha}/`, geojsonUrl: `${server.origin}/first.geojson`, dateLabel: 'May 1, 2024', displayDateLabel: 'May 1, 2024 10:00', timestampLabel: 'May 1, 2024 at 10:00 UTC', message: 'Initial survey', authorName: 'Diver' },
        ],
    };
    return { ...value, selectedRevision: value.revisions[1]! };
}

function markup() {
    document.body.innerHTML = `
        <div id="map"></div>
        <section id="revision-timeline">
          <button id="revision-play"><span id="revision-play-label">Play</span><span class="revision-play-icon"></span><span class="revision-pause-icon" hidden></span></button>
          <button id="revision-previous">Previous</button><button id="revision-next">Next</button>
          <input id="revision-seek" type="range" min="0" max="1" value="0">
          <input id="revision-speed" type="range" min="-1" max="1" step="0.01" value="0"><output id="revision-speed-value"></output>
          <span id="revision-date"></span><span id="revision-position"></span><span id="revision-message"></span><span id="revision-author"></span>
          <button id="revision-details">View details</button><div id="revision-status"></div><div id="revision-announcement" aria-live="polite"></div>
          <button id="revision-retry" hidden>Retry</button><a id="revision-reload" hidden>Reload page</a><button id="revision-cancel" hidden>Cancel</button>
          <div id="revision-pending" hidden></div><div id="revision-summary"></div><div id="revision-first-date"></div><div id="revision-last-date"></div><div id="revision-ticks"></div><div id="revision-playhead"></div><div id="revision-tooltip" role="tooltip" hidden></div>
        </section>
        <details class="historical-revisions" open><summary>Project History</summary><nav class="historical-revision-list">
          <a class="historical-revision" data-commit-sha="${nextSha}" data-geojson-url="${server.origin}/next.geojson" href="/revisions/${nextSha}/">Next</a>
          <a class="historical-revision is-selected" aria-current="page" data-commit-sha="${initialSha}" data-geojson-url="${server.origin}/first.geojson" href="/revisions/${initialSha}/">First</a>
        </nav><div id="revision-detail-content" tabindex="-1" hidden><span data-revision-detail-date></span><span data-revision-detail-message></span><span data-revision-detail-author></span><span data-revision-detail-sha></span></div></details>
        <div id="revision-playback-metadata" hidden><span id="revision-playback-date"></span><span id="revision-playback-message"></span><span id="revision-playback-author"></span></div>
        <button id="map-settings-button">Settings</button>`;
}

// JSDOM has no WebGL renderer. Only its displayed-source boundary is replaced;
// selection, timing, native DOM controls, URL history, fetch and abort remain real.
function renderer(): RevisionPlaybackViewer & { pending: Set<Promise<boolean>> } {
    const pending = new Set<Promise<boolean>>();
    return {
        pending, ready: Promise.resolve(true), stopCamera() {},
        showProject(project: ProjectMapInput, options = {}) {
            const operation = (async () => {
                try {
                    const response = await fetch(project.geojson_file!, { signal: options.signal ?? null });
                    if (!response.ok) return false;
                    await response.json();
                    if (options.signal?.aborted) return false;
                    options.onDisplayed?.();
                    return true;
                } catch (error) {
                    if (error instanceof Error && error.name === 'AbortError') return false;
                    throw error;
                }
            })();
            pending.add(operation);
            void operation.finally(() => pending.delete(operation));
            return operation;
        },
    };
}

function button(id: string) { return document.getElementById(id) as HTMLButtonElement; }
function changeSpeed(value: string) {
    const control = document.getElementById('revision-speed') as HTMLInputElement;
    control.value = String(Math.log10(Number(value)));
    control.dispatchEvent(new Event('input', { bubbles: true }));
}

beforeAll(async () => { server = await startApiServer(); });
afterAll(async () => { await server.close(); });
beforeEach(() => {
    server.reset(); server.reply({ json: survey });
    setBrowserUrl(`${server.origin}/revisions/${initialSha}/`);
    markup();
    // JSDOM has no layout/scrolling implementation; native scrolling is covered in browser workflows.
    document.querySelectorAll<HTMLElement>('.historical-revision').forEach(element => { element.scrollIntoView = () => {}; });
});
afterEach(() => { stopPlayback?.(); stopPlayback = undefined; document.body.innerHTML = ''; });

it.each([
    { mapWidth: 1200, playerWidth: 760, open: true },
    { mapWidth: 360, playerWidth: 344, open: false },
])('uses the $mapWidth px map for initial history disclosure, not its compact player', ({ mapWidth, playerWidth, open }) => {
    // JSDOM has no layout engine. Supply only the native measurements used by
    // this responsive behavior; DOM controls and disclosure state remain real.
    document.getElementById('revision-timeline')!.getBoundingClientRect = () => new DOMRect(0, 0, playerWidth, 106);
    document.getElementById('map')!.getBoundingClientRect = () => new DOMRect(0, 0, mapWidth, 800);
    const playback = initRevisionPlayback(context(), renderer());
    stopPlayback = playback.destroy;
    expect(document.querySelector<HTMLDetailsElement>('.historical-revisions')!.open).toBe(open);
});

it('offers pause during playback and holds the displayed revision when its pending download is canceled', async () => {
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    server.handle(async () => { await gate; return { json: survey }; });
    const viewer = renderer();
    const playback = initRevisionPlayback(context(), viewer);
    stopPlayback = () => playback?.destroy();
    try {
        await vi.waitFor(() => expect(button('revision-play').disabled).toBe(false));
        changeSpeed('2');
        button('revision-play').click();
        expect(document.getElementById('revision-play-label')!.textContent).toBe('Pause');
        expect(document.querySelector<HTMLElement>('.historical-revisions')!.hidden).toBe(true);
        expect(document.getElementById('revision-playback-date')!.textContent).toBe('May 1, 2024 10:00');
        await vi.waitFor(() => expect(server.requests).toHaveLength(1), { timeout: 3000 });
        expect(document.getElementById('revision-date')!.textContent).toBe('May 1, 2024');
        button('revision-play').click();
        release();
        await Promise.all(viewer.pending);
        expect(document.getElementById('revision-play-label')!.textContent).toBe('Play');
        expect(document.querySelector<HTMLElement>('.historical-revisions')!.hidden).toBe(false);
        expect(document.getElementById('revision-playback-metadata')!.hidden).toBe(true);
        expect(document.querySelector('[aria-current="page"]')!.getAttribute('data-commit-sha')).toBe(initialSha);
        expect(location.pathname).toBe(`/revisions/${initialSha}/`);
    } finally { release(); }
});

function playheadPosition() {
    return Number.parseFloat(document.getElementById('revision-timeline')!.style.getPropertyValue('--revision-playhead-position'));
}

it('keeps elapsed progress across speed changes and pause while the displayed revision stays exact', async () => {
    const playback = initRevisionPlayback(context(), renderer());
    stopPlayback = playback.destroy;
    await vi.waitFor(() => expect(button('revision-play').disabled).toBe(false));
    expect(document.querySelectorAll('.revision-tick')).toHaveLength(2);
    expect((document.getElementById('revision-speed') as HTMLInputElement).value).toBe('0');
    expect(document.getElementById('revision-speed-value')!.textContent).toBe('1×');
    expect(document.getElementById('revision-timeline')!.style.getPropertyValue('--revision-speed-position')).toBe('50%');
    // Observe actual frames at slow speed so polling cannot miss the partial
    // progress needed to exercise pause/resume during a short default dwell.
    changeSpeed('0.1');
    expect(document.getElementById('revision-speed-value')!.textContent).toBe('0.1×');
    button('revision-play').click();
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
    const beforeSpeedChange = playheadPosition();
    expect(beforeSpeedChange).toBeGreaterThan(0);
    changeSpeed('1');
    expect(document.getElementById('revision-speed-value')!.textContent).toBe('1×');
    expect(playheadPosition()).toBeGreaterThanOrEqual(beforeSpeedChange);
    expect(document.querySelector('.revision-tick.is-current')!.getAttribute('data-revision-index')).toBe('0');
    button('revision-play').click();
    const paused = playheadPosition();
    expect(paused).toBeGreaterThan(0);
    expect(paused).toBeLessThan(100);
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
    expect(playheadPosition()).toBe(paused);
    button('revision-play').click();
    expect(playheadPosition()).toBe(paused);
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
    expect(playheadPosition()).toBeGreaterThan(paused);
    expect(location.pathname).toBe(`/revisions/${initialSha}/`);
});

it('stops at the last revision and keeps Play as the explicit restart action', async () => {
    const playback = initRevisionPlayback(context(), renderer());
    stopPlayback = playback.destroy;
    await vi.waitFor(() => expect(button('revision-play').disabled).toBe(false));
    changeSpeed('10');
    button('revision-play').click();
    await vi.waitFor(() => expect(location.pathname).toBe(`/revisions/${nextSha}/`));
    expect(document.getElementById('revision-play-label')!.textContent).toBe('Play');
    expect(document.querySelector<HTMLElement>('.historical-revisions')!.hidden).toBe(false);
    expect(playheadPosition()).toBe(100);
    expect(server.requests).toHaveLength(1);
    button('revision-play').click();
    await vi.waitFor(() => expect(server.requests.some(request => request.path === '/first.geojson')).toBe(true));
});

it('restores the displayed revision URL when a pending browser navigation is canceled', async () => {
    const viewer = renderer();
    const playback = initRevisionPlayback(context(), viewer);
    stopPlayback = playback.destroy;
    await vi.waitFor(() => expect(button('revision-play').disabled).toBe(false));
    button('revision-next').click();
    await vi.waitFor(() => expect(location.pathname).toBe(`/revisions/${nextSha}/`));
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    server.handle(async () => { await gate; return { json: survey }; });
    try {
        history.back();
        await vi.waitFor(() => expect(server.requests).toHaveLength(2));
        expect(location.pathname).toBe(`/revisions/${initialSha}/`);
        button('revision-cancel').click();
        expect(location.pathname).toBe(`/revisions/${nextSha}/`);
        expect(document.querySelector('[aria-current="page"]')!.getAttribute('data-commit-sha')).toBe(nextSha);
    } finally {
        release();
        await Promise.all(viewer.pending);
    }
});

it('keeps controls usable after a page is restored from the back-forward cache', async () => {
    const playback = initRevisionPlayback(context(), renderer());
    stopPlayback = playback.destroy;
    await vi.waitFor(() => expect(button('revision-play').disabled).toBe(false));
    button('revision-play').click();
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));
    expect(document.getElementById('revision-play-label')!.textContent).toBe('Play');
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
    button('revision-next').click();
    await vi.waitFor(() => expect(location.pathname).toBe(`/revisions/${nextSha}/`));
});

it('preserves a newer browser navigation while canceling the previous pending destination', async () => {
    const value = context();
    const lastSha = 'c'.repeat(40);
    value.revisions.unshift({
        ...value.revisions[0]!, commitSha: lastSha, url: `/revisions/${lastSha}/`,
        geojsonUrl: `${server.origin}/last.geojson`,
    });
    const viewer = renderer();
    const playback = initRevisionPlayback(value, viewer);
    stopPlayback = playback.destroy;
    await vi.waitFor(() => expect(button('revision-play').disabled).toBe(false));
    button('revision-next').click();
    await vi.waitFor(() => expect(location.pathname).toBe(`/revisions/${nextSha}/`));
    button('revision-next').click();
    await vi.waitFor(() => expect(location.pathname).toBe(`/revisions/${lastSha}/`));
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    server.handle(async () => { await gate; return { json: survey }; });
    try {
        history.back();
        await vi.waitFor(() => expect(server.requests).toHaveLength(3));
        history.back();
        await vi.waitFor(() => expect(server.requests).toHaveLength(4));
        release();
        await Promise.all(viewer.pending);
        await vi.waitFor(() => expect(document.querySelector('[aria-current="page"]')!.getAttribute('data-commit-sha')).toBe(initialSha));
        expect(location.pathname).toBe(`/revisions/${initialSha}/`);
    } finally {
        release();
        await Promise.all(viewer.pending);
    }
});
