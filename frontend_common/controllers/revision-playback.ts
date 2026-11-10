import type { ProjectMapRevision, ProjectRevisionMapContext } from '../../ts-types/controllers/project-revision-map.ts';
import type { ProjectMapInput } from '../../ts-types/domain/map-config.ts';
import { DEFAULTS } from '../../frontend_private/static/private/ts/map_viewer/defaults.ts';
import { State } from '../../frontend_private/static/private/ts/map_viewer/state.ts';

export interface RevisionPlaybackViewer {
    ready: Promise<boolean>;
    showProject(project: ProjectMapInput, options?: {
        signal?: AbortSignal;
        camera?: 'fit' | 'preserve' | 'follow';
        cameraDurationMs?: number;
        onDisplayed?: () => void;
    }): Promise<boolean>;
    stopCamera(): void;
}

type SelectionKind = 'manual' | 'playback' | 'navigation';
interface PendingRevision {
    revision: ProjectMapRevision;
    controller: AbortController;
    committed: boolean;
    kind: SelectionKind;
}

/**
 * Historical playback owns the revision-* controls, data-revision-index dots,
 * and data-commit-sha history links. These are runtime/test hooks; CSS classes
 * own presentation. Progress is elapsed playback time, never invented geometry.
 */
export function initRevisionPlayback(context: ProjectRevisionMapContext, viewer: RevisionPlaybackViewer) {
    const timeline = document.getElementById('revision-timeline');
    const list = document.querySelector<HTMLElement>('.historical-revision-list');
    const panel = document.querySelector<HTMLDetailsElement>('.historical-revisions');
    const play = document.getElementById('revision-play') as HTMLButtonElement | null;
    const previous = document.getElementById('revision-previous') as HTMLButtonElement | null;
    const next = document.getElementById('revision-next') as HTMLButtonElement | null;
    const seek = document.getElementById('revision-seek') as HTMLInputElement | null;
    const speedControl = document.getElementById('revision-speed') as HTMLInputElement | null;
    const ticks = document.getElementById('revision-ticks');
    const tooltip = document.getElementById('revision-tooltip');
    const detailsButton = document.getElementById('revision-details');
    const detailContent = document.getElementById('revision-detail-content');
    const overlay = document.getElementById('revision-playback-metadata');
    const revisions = [...context.revisions].reverse().filter(revision => revision.available && revision.geojsonUrl);
    const initialRevision = context.selectedRevision;
    const listeners = new AbortController();
    const minimumSpeedScale = Math.log10(DEFAULTS.HISTORY.MIN_SPEED);
    const maximumSpeedScale = Math.log10(DEFAULTS.HISTORY.MAX_SPEED);
    let displayed: ProjectMapRevision | null = null;
    let pending: PendingRevision | null = null;
    let previewIndex: number | null = null;
    let failed: ProjectMapRevision | null = null;
    let playing = false;
    let initialized = false;
    let disposed = false;
    let speed: number = DEFAULTS.HISTORY.DEFAULT_SPEED;
    let speedScale = Math.log10(speed);
    let fraction = 0;
    let lastFrameTime: number | null = null;
    let frame: number | null = null;
    let slowTimer: ReturnType<typeof setTimeout> | null = null;
    let slow = false;
    let playbackHistoryStarted = false;
    let listInteracting = false;
    let panelHiddenBeforePlayback: HTMLElement['hidden'] = false;

    function text(id: string, value: string) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }
    function hidden(id: string, value: boolean) {
        const element = document.getElementById(id);
        if (element) element.hidden = value;
    }
    function announce(message: string) { text('revision-announcement', message); }
    function indexOf(revision: ProjectMapRevision | null) {
        return revision ? revisions.findIndex(item => item.commitSha === revision.commitSha) : -1;
    }
    function position(index: number) {
        return revisions.length > 1 ? index / (revisions.length - 1) * 100 : 50;
    }
    function describe(revision: ProjectMapRevision) {
        const index = indexOf(revision);
        return `${index >= 0 ? `Revision ${index + 1} of ${revisions.length}, ` : ''}${revision.timestampLabel}`;
    }
    function paintProgress() {
        const index = indexOf(displayed);
        timeline?.style.setProperty('--revision-playhead-position', `${position(Math.max(0, index) + fraction)}%`);
    }
    function captureProgress(now: number) {
        const timestamp = Math.max(now, lastFrameTime ?? now);
        if (playing && lastFrameTime !== null && (!pending || pending.committed)) {
            fraction = Math.min(1, fraction + (timestamp - lastFrameTime) * speed / DEFAULTS.HISTORY.DWELL_MS);
        }
        lastFrameTime = timestamp;
        paintProgress();
    }
    function clearSlowTimer() {
        if (slowTimer !== null) clearTimeout(slowTimer);
        slowTimer = null;
    }
    function setPlaying(value: boolean) {
        if (value && !playing) {
            panelHiddenBeforePlayback = panel?.hidden ?? false;
            if (panel) panel.hidden = true;
        } else if (!value && playing) {
            if (panel) panel.hidden = panelHiddenBeforePlayback;
        }
        playing = value;
        if (!value) {
            if (frame !== null) cancelAnimationFrame(frame);
            frame = null;
            lastFrameTime = null;
        }
    }
    function updateDetails(revision: ProjectMapRevision) {
        for (const [name, value] of Object.entries({ date: revision.timestampLabel, message: revision.message, author: revision.authorName, sha: revision.commitSha })) {
            const element = detailContent?.querySelector<HTMLElement>(`[data-revision-detail-${name}]`);
            if (element) element.textContent = value;
        }
    }
    function render() {
        const currentIndex = indexOf(displayed);
        const busy = !!pending && !pending.committed;
        const targetIndex = previewIndex ?? (busy ? indexOf(pending!.revision) : currentIndex);
        const target = targetIndex >= 0 ? revisions[targetIndex] : null;
        const end = displayed !== null && currentIndex === revisions.length - 1;
        const playable = initialized && displayed !== null && revisions.length > 1;
        text('revision-play-label', playing ? 'Pause' : 'Play');
        if (play) {
            play.disabled = !playable || (busy && !playing);
            play.setAttribute('aria-label', playing ? 'Pause history' : end ? 'Play history from the beginning' : 'Play history');
            play.setAttribute('aria-pressed', String(playing));
            play.title = !playing && end ? 'Play history from the beginning' : playing ? 'Pause' : 'Play';
        }
        play?.querySelector('.revision-play-icon')?.toggleAttribute('hidden', playing);
        play?.querySelector('.revision-pause-icon')?.toggleAttribute('hidden', !playing);
        if (previous) previous.disabled = currentIndex <= 0;
        if (next) next.disabled = revisions.length === 0 || currentIndex === revisions.length - 1;
        if (seek) {
            seek.disabled = revisions.length <= 1;
            seek.max = String(Math.max(0, revisions.length - 1));
            const value = String(Math.max(0, targetIndex));
            if (seek.value !== value) seek.value = value;
            seek.setAttribute('aria-valuetext', target ? `${describe(target)}${busy || previewIndex !== null ? ', not yet displayed' : ''}` : 'No mapped revisions');
        }
        if (speedControl) {
            const label = `${Number(speed.toPrecision(DEFAULTS.HISTORY.SPEED_LABEL_DIGITS))}×`;
            speedControl.disabled = !playable;
            speedControl.value = String(speedScale);
            speedControl.setAttribute('aria-valuetext', `${label} speed`);
            speedControl.title = `${label} speed`;
            text('revision-speed-value', label);
            timeline?.style.setProperty('--revision-speed-position', `${(speedScale - minimumSpeedScale) / (maximumSpeedScale - minimumSpeedScale) * 100}%`);
        }
        const metadata = displayed ?? initialRevision;
        text('revision-date', metadata.dateLabel);
        text('revision-message', metadata.message);
        text('revision-author', metadata.authorName ? `by ${metadata.authorName}` : '');
        text('revision-position', displayed === null ? 'Preparing' : currentIndex >= 0 ? `${currentIndex + 1} / ${revisions.length}` : 'Outside timeline');
        document.getElementById('revision-position')?.setAttribute('aria-label', displayed ? describe(displayed) : 'Requested revision not yet displayed');
        detailsButton?.setAttribute('aria-label', `View details for ${describe(metadata)}`);
        updateDetails(metadata);
        if (overlay) overlay.hidden = !playing || displayed === null;
        if (displayed) {
            text('revision-playback-date', displayed.displayDateLabel);
            text('revision-playback-message', displayed.message);
            text('revision-playback-author', displayed.authorName ? `by ${displayed.authorName}` : '');
            document.getElementById('revision-playback-message')?.setAttribute('title', displayed.message);
            document.getElementById('revision-playback-author')?.setAttribute('title', displayed.authorName);
        }
        timeline?.classList.toggle('is-playing', playing);
        timeline?.classList.toggle('is-pending', previewIndex !== null || (busy && !playing));
        timeline?.classList.toggle('is-buffering', busy && playing);
        timeline?.classList.toggle('has-error', failed !== null);
        timeline?.setAttribute('aria-busy', String(busy || !initialized));
        hidden('revision-playhead', currentIndex < 0);
        if (currentIndex >= 0) timeline?.style.setProperty('--revision-current-position', `${position(currentIndex)}%`);
        if (targetIndex >= 0) timeline?.style.setProperty('--revision-pending-position', `${position(targetIndex)}%`);
        hidden('revision-pending', !target || (!busy && previewIndex === null) || (playing && !slow));
        text('revision-pending', target ? `${previewIndex !== null ? 'Preview' : 'Requested'}: ${target.displayDateLabel}` : '');
        hidden('revision-retry', failed === null);
        hidden('revision-reload', failed === null);
        hidden('revision-cancel', (!busy || playing) && previewIndex === null);
        if (busy) list?.setAttribute('aria-busy', 'true');
        else list?.removeAttribute('aria-busy');
        for (const link of list?.querySelectorAll<HTMLAnchorElement>('a.historical-revision') ?? []) {
            const selected = displayed?.commitSha === link.dataset.commitSha;
            link.classList.toggle('is-selected', selected);
            link.classList.toggle('is-pending', busy && pending!.revision.commitSha === link.dataset.commitSha);
            if (selected) link.setAttribute('aria-current', 'page');
            else link.removeAttribute('aria-current');
        }
        const focusedTick = document.activeElement instanceof HTMLElement && ticks?.contains(document.activeElement) ? document.activeElement : null;
        for (const tick of ticks?.querySelectorAll<HTMLButtonElement>('.revision-tick') ?? []) {
            const index = Number(tick.dataset.revisionIndex);
            tick.classList.toggle('is-current', index === currentIndex);
            tick.classList.toggle('is-past', index < currentIndex);
            tick.tabIndex = focusedTick ? (tick === focusedTick ? 0 : -1) : index === Math.max(0, currentIndex) ? 0 : -1;
            if (index === currentIndex) tick.setAttribute('aria-current', 'step');
            else tick.removeAttribute('aria-current');
        }
        let status = '';
        if (!initialized) status = 'Preparing the survey map…';
        else if (failed) status = 'Couldn’t load this revision.';
        else if (busy && (!playing || slow)) status = slow ? 'Loading revision…' : 'Preparing revision…';
        else if (previewIndex !== null) status = 'Release to view this revision';
        else if (!busy && displayed && !State.projectBounds.has(context.project.id)) status = 'No survey geometry in this revision.';
        else if (revisions.length === 0) status = 'No mapped revisions in this history.';
        else if (revisions.length === 1) status = 'One mapped revision.';
        text('revision-status', status);
        timeline?.classList.toggle('has-feedback', status !== '');
        paintProgress();
    }
    function cancelPending(restoreNavigation = true) {
        if (pending && !pending.committed) {
            pending.controller.abort();
            if (restoreNavigation && pending.kind === 'navigation' && displayed) {
                history.replaceState(null, '', displayed.url);
            }
        }
        pending = null;
        previewIndex = null;
        clearSlowTimer();
        viewer.stopCamera();
    }
    function pause(message = 'Playback paused', options: { restoreNavigation?: boolean; previewIndex?: number } = {}) {
        const wasPlaying = playing;
        if (playing) captureProgress(performance.now());
        setPlaying(false);
        cancelPending(options.restoreNavigation);
        previewIndex = options.previewIndex ?? null;
        if (wasPlaying || message !== 'Playback paused') announce(message);
        render();
    }
    function queueFrame() {
        if (frame !== null || !playing || disposed || (pending && !pending.committed)) return;
        frame = requestAnimationFrame(() => {
            frame = null;
            if (!playing || disposed) return;
            // Frames and control events must measure elapsed time on the same clock.
            captureProgress(performance.now());
            if (fraction >= 1) {
                if (!pending) {
                    const revision = revisions[indexOf(displayed) + 1];
                    if (revision) void selectRevision(revision, 'playback');
                }
                return;
            }
            queueFrame();
        });
    }
    function commit(selection: PendingRevision) {
        if (disposed || pending !== selection || selection.controller.signal.aborted) return;
        selection.committed = true;
        displayed = selection.revision;
        initialized = true;
        failed = null;
        fraction = 0;
        lastFrameTime = performance.now();
        if (selection.kind === 'manual') history.pushState(null, '', displayed.url);
        else if (selection.kind === 'playback') {
            if (playbackHistoryStarted) history.replaceState(null, '', displayed.url);
            else { history.pushState(null, '', displayed.url); playbackHistoryStarted = true; }
        }
        if (selection.kind !== 'playback') announce(`Displayed ${describe(displayed)}`);
        if (playing && indexOf(displayed) === revisions.length - 1) {
            setPlaying(false);
        }
        render();
        queueFrame();
        if (!playing && !listInteracting && panel?.open) {
            const link = [...list?.querySelectorAll<HTMLAnchorElement>('a.historical-revision') ?? []]
                .find(item => item.dataset.commitSha === displayed?.commitSha);
            link?.scrollIntoView({ block: 'nearest' });
        }
    }
    async function selectRevision(revision: ProjectMapRevision, kind: SelectionKind) {
        if (!revision.available || !revision.geojsonUrl || disposed) return;
        cancelPending();
        if (displayed?.commitSha === revision.commitSha) { failed = null; render(); queueFrame(); return; }
        const selection: PendingRevision = { revision, controller: new AbortController(), committed: false, kind };
        pending = selection;
        failed = null;
        slow = false;
        render();
        slowTimer = setTimeout(() => {
            if (pending === selection && !selection.committed) {
                slow = true;
                announce(playing ? 'Loading next revision' : `Loading ${revision.dateLabel}`);
                render();
            }
        }, DEFAULTS.HISTORY.SLOW_LOAD_MS);
        try {
            const success = await viewer.showProject({ ...context.project, geojson_file: revision.geojsonUrl }, {
                signal: selection.controller.signal,
                camera: 'follow',
                ...(kind === 'playback' ? { cameraDurationMs: DEFAULTS.HISTORY.DWELL_MS / speed } : {}),
                onDisplayed: () => commit(selection),
            });
            if (pending !== selection || disposed) return;
            if (!success) {
                failed = revision;
                setPlaying(false);
                if (kind === 'navigation' && displayed) history.replaceState(null, '', displayed.url);
                announce('Couldn’t load this revision. Retry or choose another revision.');
            }
        } catch (error) {
            if (pending !== selection || disposed || selection.controller.signal.aborted) return;
            console.error('Failed to select historical revision', error);
            failed = revision;
            setPlaying(false);
            if (kind === 'navigation' && displayed) history.replaceState(null, '', displayed.url);
            announce('Couldn’t load this revision. Retry or choose another revision.');
        } finally {
            if (pending === selection) {
                pending = null;
                clearSlowTimer();
                render();
                queueFrame();
            }
        }
    }
    function manualSelect(index: number) {
        pause();
        fraction = 0;
        const revision = revisions[index];
        if (revision) void selectRevision(revision, 'manual');
    }
    function setSpeedScale(value: string) {
        const candidate = Number(value);
        if (!Number.isFinite(candidate) || candidate < minimumSpeedScale || candidate > maximumSpeedScale) return;
        if (playing) captureProgress(performance.now());
        speedScale = candidate;
        speed = 10 ** speedScale;
        render();
        queueFrame();
    }
    function showTooltip(index: number) {
        const revision = revisions[index];
        if (!revision || !tooltip) return;
        tooltip.textContent = `${revision.displayDateLabel} · ${revision.message}${revision.authorName ? ` · by ${revision.authorName}` : ''}`;
        tooltip.hidden = false;
        timeline?.style.setProperty('--revision-tooltip-position', `${position(index)}%`);
    }
    function hideTooltip() { if (tooltip) tooltip.hidden = true; }
    function createTicks() {
        if (!ticks) return;
        const fragment = document.createDocumentFragment();
        revisions.forEach((revision, index) => {
            const tick = document.createElement('button');
            tick.type = 'button';
            tick.className = 'revision-tick';
            tick.dataset.revisionIndex = String(index);
            tick.style.left = `${position(index)}%`;
            tick.setAttribute('aria-label', `${describe(revision)}. ${revision.message}${revision.authorName ? `. By ${revision.authorName}` : ''}`);
            tick.setAttribute('aria-describedby', 'revision-tooltip');
            fragment.append(tick);
        });
        ticks.replaceChildren(fragment);
    }

    play?.addEventListener('click', () => {
        if (playing) { pause(); return; }
        setPlaying(true);
        playbackHistoryStarted = false;
        failed = null;
        detailContent?.setAttribute('hidden', '');
        detailsButton?.setAttribute('aria-expanded', 'false');
        hideTooltip();
        announce('Playing history');
        lastFrameTime = performance.now();
        render();
        if (indexOf(displayed) === revisions.length - 1 || indexOf(displayed) < 0) {
            const first = revisions[0];
            if (first) void selectRevision(first, 'playback');
        } else queueFrame();
    }, { signal: listeners.signal });
    previous?.addEventListener('click', () => manualSelect(indexOf(displayed) - 1), { signal: listeners.signal });
    next?.addEventListener('click', () => manualSelect(indexOf(displayed) + 1), { signal: listeners.signal });
    seek?.addEventListener('pointerdown', () => pause(), { signal: listeners.signal });
    seek?.addEventListener('input', () => {
        const index = Number(seek.value);
        // Preserve the native value throughout the gesture. Resetting it while
        // pausing causes WebKit to lose the range's eventual change event.
        pause('Playback paused', { previewIndex: index });
        showTooltip(index);
    }, { signal: listeners.signal });
    seek?.addEventListener('change', () => { manualSelect(Number(seek.value)); hideTooltip(); }, { signal: listeners.signal });
    seek?.addEventListener('focus', () => showTooltip(Number(seek.value)), { signal: listeners.signal });
    seek?.addEventListener('blur', hideTooltip, { signal: listeners.signal });
    seek?.addEventListener('pointermove', event => {
        const bounds = ticks?.getBoundingClientRect();
        if (!bounds?.width) return;
        const index = Math.round((event.clientX - bounds.left) / bounds.width * (revisions.length - 1));
        showTooltip(Math.max(0, Math.min(revisions.length - 1, index)));
    }, { signal: listeners.signal });
    seek?.addEventListener('pointerleave', hideTooltip, { signal: listeners.signal });
    speedControl?.addEventListener('input', () => setSpeedScale(speedControl.value), { signal: listeners.signal });
    ticks?.addEventListener('click', event => {
        const tick = event.target instanceof Element ? event.target.closest<HTMLButtonElement>('.revision-tick') : null;
        if (tick) { manualSelect(Number(tick.dataset.revisionIndex)); hideTooltip(); }
    }, { signal: listeners.signal });
    for (const eventName of ['pointerover', 'focusin'] as const) ticks?.addEventListener(eventName, event => {
        const tick = event.target instanceof Element ? event.target.closest<HTMLButtonElement>('.revision-tick') : null;
        if (tick) showTooltip(Number(tick.dataset.revisionIndex));
    }, { signal: listeners.signal });
    ticks?.addEventListener('pointerleave', hideTooltip, { signal: listeners.signal });
    ticks?.addEventListener('focusout', hideTooltip, { signal: listeners.signal });
    ticks?.addEventListener('keydown', event => {
        const tick = event.target instanceof HTMLElement ? event.target.closest<HTMLButtonElement>('.revision-tick') : null;
        if (!tick) return;
        const index = Number(tick.dataset.revisionIndex);
        const target = event.key === 'ArrowLeft' ? index - 1 : event.key === 'ArrowRight' ? index + 1 : event.key === 'Home' ? 0 : event.key === 'End' ? revisions.length - 1 : null;
        if (target === null) return;
        event.preventDefault();
        const buttons = ticks.querySelectorAll<HTMLButtonElement>('.revision-tick');
        const destination = buttons[Math.max(0, Math.min(revisions.length - 1, target))];
        if (destination) { tick.tabIndex = -1; destination.tabIndex = 0; destination.focus({ preventScroll: true }); }
    }, { signal: listeners.signal });
    document.getElementById('revision-cancel')?.addEventListener('click', () => pause('Selection canceled'), { signal: listeners.signal });
    document.getElementById('revision-retry')?.addEventListener('click', () => {
        const revision = failed;
        pause();
        if (revision) void selectRevision(revision, 'manual');
    }, { signal: listeners.signal });
    document.getElementById('revision-reload')?.addEventListener('click', () => location.reload(), { signal: listeners.signal });
    timeline?.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            hideTooltip();
            if (pending || previewIndex !== null) { event.preventDefault(); pause('Selection canceled'); }
        }
    }, { signal: listeners.signal });
    detailsButton?.addEventListener('click', () => {
        pause();
        if (panel) panel.open = true;
        if (detailContent) {
            detailContent.hidden = false;
            detailsButton.setAttribute('aria-expanded', 'true');
            detailContent.focus({ preventScroll: true });
        }
    }, { signal: listeners.signal });
    document.getElementById('revision-detail-close')?.addEventListener('click', () => {
        if (detailContent) detailContent.hidden = true;
        detailsButton?.setAttribute('aria-expanded', 'false');
        detailsButton?.focus({ preventScroll: true });
    }, { signal: listeners.signal });
    list?.addEventListener('click', event => {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>('a.historical-revision') : null;
        if (!link || !list.contains(link)) return;
        const revision = revisions.find(item => item.commitSha === link.dataset.commitSha);
        if (!revision) return;
        event.preventDefault();
        pause();
        fraction = 0;
        void selectRevision(revision, 'manual');
    }, { signal: listeners.signal });
    list?.addEventListener('pointerenter', () => { listInteracting = true; }, { signal: listeners.signal });
    list?.addEventListener('pointerleave', () => { listInteracting = list.contains(document.activeElement); }, { signal: listeners.signal });
    list?.addEventListener('focusin', () => { listInteracting = true; }, { signal: listeners.signal });
    list?.addEventListener('focusout', event => { listInteracting = event.relatedTarget instanceof Node && list.contains(event.relatedTarget); }, { signal: listeners.signal });
    document.getElementById('map-settings-button')?.addEventListener('click', () => pause(), { signal: listeners.signal });
    document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); }, { signal: listeners.signal });
    window.addEventListener('popstate', () => {
        pause('Playback paused', { restoreNavigation: false });
        fraction = 0;
        const revision = [context.selectedRevision, ...context.revisions].find(item => new URL(item.url, location.href).pathname.toLowerCase() === location.pathname.toLowerCase());
        if (revision?.available) void selectRevision(revision, 'navigation');
    }, { signal: listeners.signal });
    window.addEventListener('pagehide', event => {
        if (event.persisted) pause();
        else destroy();
    }, { signal: listeners.signal });

    const availableWidth = document.getElementById('map')?.getBoundingClientRect().width || window.innerWidth;
    if (panel && availableWidth <= DEFAULTS.HISTORY.MOBILE_BREAKPOINT) panel.open = false;
    if (speedControl) {
        speedControl.min = String(minimumSpeedScale);
        speedControl.max = String(maximumSpeedScale);
        speedControl.step = String(DEFAULTS.HISTORY.SPEED_SCALE_STEP);
    }
    text('revision-first-date', revisions[0]?.dateLabel ?? 'First map');
    text('revision-last-date', revisions.at(-1)?.dateLabel ?? 'Latest map');
    const missing = context.revisions.length - revisions.length;
    text('revision-summary', `${revisions.length} mapped revision${revisions.length === 1 ? '' : 's'}${missing ? ` · ${missing} without maps` : ''}`);
    createTicks();
    render();
    void viewer.ready.then(success => {
        if (disposed) return;
        initialized = true;
        if (!displayed) {
            if (success) displayed = initialRevision;
            else if (!pending) { failed = initialRevision; announce('Couldn’t load the initial revision. Retry or choose another revision.'); }
        }
        render();
    });

    function destroy() {
        if (disposed) return;
        disposed = true;
        setPlaying(false);
        cancelPending();
        listeners.abort();
    }
    return { destroy };
}
