import type { UserExportsContext } from '../../ts-types/controllers/user-exports.ts';
import type { ExportHistoryOptions, ExportJob, ExportOmission, ExportPage, ExportRequestFailure, ExportState } from '../../ts-types/domain/exports.ts';

const POLL_INTERVAL_MS = 5000;
const MAX_REFRESH_FAILURES = 5;
const MAX_RETRY_DELAY_MS = 30_000;
const REQUEST_TIMEOUT_MS = 30_000;
const MAX_TIMER_DELAY_MS = 2 ** 31 - 1;
const ACTIVE_STATES = new Set(['queued', 'running', 'retry_wait']);
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const STATE_LABELS = {
    queued: 'Queued',
    running: 'Generating export',
    retry_wait: 'Waiting to retry',
    ready: 'Ready to download',
    partial: 'Ready with omissions',
    failed: 'Export failed',
    cancelled: 'Export cancelled',
};
const STATE_CLASSES: Partial<Record<ExportState, string>> = {
    queued: 'exports-badge-active',
    running: 'exports-badge-active',
    retry_wait: 'exports-badge-active',
    ready: 'exports-badge-ready',
    partial: 'exports-badge-warning',
    failed: 'exports-badge-failed',
};
const SIZE_UNITS = ['bytes', 'KB', 'MB', 'GB', 'TB'];
const SIZE_UNIT_BASE = 1000;
const ICON_PATHS = {
    archive: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M10 12h4 M10 16h4',
    download: 'M12 3v12m-4-4 4 4 4-4 M5 16v4a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4',
    retry: 'M3 10a9 9 0 1 1 2 8 M3 4v6h6',
};

function element<Tag extends keyof HTMLElementTagNameMap>(tag: Tag, text?: string, className = '') {
    const node = document.createElement(tag);
    node.textContent = text as string;
    node.className = className;
    return node;
}

function dateLabel(value: string | undefined) {
    const date = new Date(value as string);
    return Number.isNaN(date.getTime()) ? 'Unknown date' : date.toLocaleString();
}

function sizeLabel(value: unknown) {
    const bytes = Number(value);
    if (value == null || !Number.isFinite(bytes) || bytes < 0) return 'Size unavailable';
    const unit = bytes > 0 ? Math.min(Math.floor(Math.log(bytes) / Math.log(SIZE_UNIT_BASE)), SIZE_UNITS.length - 1) : 0;
    const index = Math.max(0, unit);
    return `${(bytes / SIZE_UNIT_BASE ** index).toLocaleString(undefined, { maximumFractionDigits: 1 })} ${SIZE_UNITS[index]}`;
}

function icon(name: keyof typeof ICON_PATHS) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    for (const [attribute, value] of Object.entries({
        class: 'exports-icon', viewBox: '0 0 24 24', fill: 'none',
        stroke: 'currentColor', 'stroke-width': '1.6', 'stroke-linecap': 'round',
        'stroke-linejoin': 'round', 'aria-hidden': 'true',
    })) svg.setAttribute(attribute, value);
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', ICON_PATHS[name]);
    svg.append(path);
    return svg;
}

function action<Tag extends 'a' | 'button'>(tag: Tag, label: string, iconName: keyof typeof ICON_PATHS, className: string) {
    const control = element(tag, '', `exports-button ${className}`);
    control.append(icon(iconName), element('span', label));
    return control;
}

function omissionLabel(omission: unknown) {
    if (typeof omission === 'string') return omission;
    if (!omission || typeof omission !== 'object') return 'An item could not be included.';
    return [(omission as ExportOmission).category, (omission as ExportOmission).name, (omission as ExportOmission).reason || (omission as ExportOmission).error]
        .filter(value => typeof value === 'string' && value.length > 0).join(': ')
        || 'An item could not be included.';
}

export function requestedExportId(search: string) {
    const value = new URLSearchParams(search).get('export');
    return value && UUID_PATTERN.test(value) ? value : null;
}

async function responseData(response: Response): Promise<unknown> {
    const data: unknown = await response.json();
    if (!response.ok) {
        const error = new Error((data as { detail?: string }).detail || 'Unable to load exports. Please try again.') as ExportRequestFailure;
        error.status = response.status;
        throw error;
    }
    return data;
}

/** Bound the full request, including JSON reads, and propagate page cancellation. */
async function fetchExportData<Result>(url: string, options: RequestInit = {}): Promise<Result> {
    const controller = new AbortController();
    const cancel = () => controller.abort(options.signal!.reason);
    let rejectAborted!: (reason: unknown) => void;
    const aborted = new Promise<never>((_, reject) => { rejectAborted = reject; });
    const onAbort = () => rejectAborted(controller.signal.reason);
    controller.signal.addEventListener('abort', onAbort, { once: true });
    options.signal?.addEventListener('abort', cancel, { once: true });
    const timeout = window.setTimeout(() => {
        controller.abort(new Error('The export request timed out. Please try again.'));
    }, REQUEST_TIMEOUT_MS);
    try {
        if (options.signal?.aborted) cancel();
        return await Promise.race([
            aborted,
            Promise.resolve().then(() => {
                controller.signal.throwIfAborted();
                return fetch(url, { ...options, signal: controller.signal }).then(responseData);
            }),
        ]) as Result;
    } finally {
        window.clearTimeout(timeout);
        options.signal?.removeEventListener('abort', cancel);
        controller.signal.removeEventListener('abort', onAbort);
    }
}

/** Expiry can remove the last row of a later page; fall back once to page one. */
export async function loadExportPage(url: string, firstPageUrl: string, options?: RequestInit) {
    try {
        return { url, data: await fetchExportData<ExportPage>(url, options) };
    } catch (error) {
        if ((error as ExportRequestFailure).status !== 404 || url === firstPageUrl) throw error;
        return { url: firstPageUrl, data: await fetchExportData<ExportPage>(firstPageUrl, options) };
    }
}

/** Keep one visible card per export, including links outside the current page. */
export function mergeExportJobs(jobs: ExportJob[], linkedJob: ExportJob | null = null, now = Date.now()) {
    const merged = new Map(jobs.map(job => [String(job.id).toLowerCase(), job]));
    if (linkedJob) {
        const id = String(linkedJob.id).toLowerCase();
        const pageJob = merged.get(id);
        // The two requests may observe different moments during a retry.
        const pageIsNewer = new Date(pageJob?.updated_at as string).getTime() > new Date(linkedJob.updated_at as string).getTime();
        if (!pageIsNewer) merged.set(id, linkedJob);
    }
    return [...merged.values()].filter(job => ACTIVE_STATES.has(job.state) || (
        !job.expired
        && !job.artifact?.deleted_at
        && !(Date.parse(job.artifact?.expires_at as string) <= now)
    ));
}

/** Refresh active work regularly and ready downloads when their availability ends. */
export function exportRefreshDelay(jobs: ExportJob[], active = false, now = Date.now()) {
    let delay = active ? POLL_INTERVAL_MS : Infinity;
    for (const job of jobs) {
        if (ACTIVE_STATES.has(job.state)) continue;
        const expiresAt = Date.parse(job.artifact?.expires_at as string);
        if (Number.isFinite(expiresAt) && expiresAt > now) {
            delay = Math.min(delay, expiresAt - now);
        }
    }
    return Number.isFinite(delay) ? Math.min(MAX_TIMER_DELAY_MS, Math.max(1, delay)) : null;
}

/**
 * Stable DOM contract: [data-export-id] identifies a history card;
 * [data-export-retry] identifies its retry control. Styles use classes only.
 * All API strings are assigned through textContent.
 */
export function renderExportHistory(container: HTMLElement, jobs: ExportJob[], { endpoint, busy = false, linkedJob = null, focusId = null, now = Date.now() }: ExportHistoryOptions = {}) {
    const visibleJobs = mergeExportJobs(jobs, linkedJob, now);
    const active = visibleJobs.some(job => ACTIVE_STATES.has(job.state));
    const previousFocus = document.activeElement;
    const previousCard = previousFocus?.closest<HTMLElement>('[data-export-id]');
    const previousId = container.contains(previousCard as HTMLElement | null) ? previousCard!.dataset.exportId!.toLowerCase() : null;
    const previousControl = previousFocus?.matches('[data-export-retry]')
        ? '[data-export-retry]' : previousFocus?.matches('a') ? 'a' : null;
    let focusTarget: HTMLElement | null = null;
    let retainedFocus: HTMLElement | null = null;
    container.replaceChildren();
    if (!visibleJobs.length) {
        const empty = element('div', '', 'exports-empty');
        const symbol = element('div', '', 'exports-empty-icon');
        symbol.append(icon('archive'));
        empty.append(symbol, element('h4', 'No current exports'));
        empty.append(element('p', 'Generate an export above. Your archive will appear here when it’s ready to download.'));
        container.append(empty);
        return false;
    }
    for (const job of visibleJobs) {
        const card = element('article', '', 'exports-card');
        card.dataset.exportId = String(job.id);
        if (focusId && String(job.id).toLowerCase() === focusId.toLowerCase()) {
            card.tabIndex = -1;
            focusTarget = card;
        }
        const main = element('div', '', 'exports-card-main');
        const symbol = element('div', '', 'exports-file-icon');
        symbol.append(icon('archive'));
        const body = element('div', '', 'exports-card-body');
        const heading = element('div', '', 'exports-card-heading');
        heading.append(element('h4', 'Data export'), element('span',
            STATE_LABELS[job.state] || 'Export status unavailable',
            `exports-badge ${STATE_CLASSES[job.state] || ''}`));
        body.append(heading, element('p', `Requested ${dateLabel(job.created_at)}`, 'exports-card-meta'));
        if (ACTIVE_STATES.has(job.state)) {
            body.append(element('p', 'An email will be sent when ready to download.', 'exports-card-description'));
        } else if (job.artifact) {
            body.append(element('p', `${sizeLabel(job.artifact.size_bytes)} · Expires ${dateLabel(job.artifact.expires_at)}`, 'exports-card-meta'));
        }
        main.append(symbol, body);
        card.append(main);
        if (job.state === 'partial') {
            const notice = element('div', '', 'exports-card-notice');
            notice.append(element('p', 'Some files could not be included. Review these omissions before relying on this backup.'));
            const omissions = Array.isArray(job.summary?.omissions) ? job.summary.omissions : [];
            if (omissions.length) {
                const list = element('ul');
                omissions.forEach(omission => list.append(element('li', omissionLabel(omission))));
                notice.append(list);
            }
            notice.append(element('p', 'The ZIP includes the full list in manifest.json.', 'exports-card-meta'));
            card.append(notice);
        }
        if (job.state === 'failed') {
            body.append(element('p', 'The export could not be completed. Retry to take a fresh snapshot of your accessible data.', 'exports-card-description'));
        }
        if (job.notification_state === 'failed') {
            card.append(element('p', 'The notification email could not be delivered. You can follow the export here.', 'exports-card-notice'));
        }
        const actions = element('div', '', 'exports-card-actions');
        if (UUID_PATTERN.test(job.id)) {
            if (job.download_url && !job.expired && ['ready', 'partial'].includes(job.state)) {
                const link = action('a', 'Download ZIP', 'download', 'exports-button-download');
                // Construct the owned route; never trust an API-provided href.
                link.href = `${endpoint}${job.id}/download/`;
                actions.append(link);
            }
            if (job.state === 'failed') {
                const retry = action('button', 'Retry export', 'retry', 'exports-button-secondary');
                retry.type = 'button';
                retry.dataset.exportRetry = job.id;
                retry.disabled = busy || active;
                actions.append(retry);
            }
        }
        if (actions.childElementCount) main.append(actions);
        if (String(job.id).toLowerCase() === previousId) {
            if (previousControl) retainedFocus = card.querySelector<HTMLElement>(previousControl);
            else if (previousFocus === previousCard) {
                card.tabIndex = -1;
                retainedFocus = card;
            }
        }
        container.append(card);
    }
    // Native focus also scrolls the linked card into view without another panel.
    if (focusTarget) focusTarget.focus();
    else retainedFocus?.focus({ preventScroll: true });
    return Boolean(focusTarget);
}

export async function init(context: UserExportsContext) {
    const root = document.getElementById('user-exports');
    if (!root) return;
    const endpoint = new URL(context.endpoint, window.location.href);
    if (endpoint.origin !== window.location.origin) throw new Error('Invalid export endpoint');
    const endpointPath = endpoint.pathname;
    const form = root.querySelector<HTMLFormElement>('#export-request-form')!;
    const create = root.querySelector<HTMLButtonElement>('#export-create')!;
    const createLabel = root.querySelector<HTMLElement>('#export-create-label')!;
    const history = root.querySelector<HTMLElement>('#export-history')!;
    const message = root.querySelector<HTMLElement>('#export-message')!;
    const previous = root.querySelector<HTMLButtonElement>('#export-previous')!;
    const next = root.querySelector<HTMLButtonElement>('#export-next')!;
    const csrfToken = form.querySelector<HTMLInputElement>('[name="csrfmiddlewaretoken"]')!.value;
    let currentUrl = endpoint.href;
    let previousUrl: string | null = null;
    let nextUrl: string | null = null;
    let jobs: ExportJob[] = [];
    let linkedId = requestedExportId(window.location.search);
    let linkedJob: ExportJob | null = null;
    let focusLinkedExport = Boolean(linkedId);
    let active = false;
    let mutationPending = false;
    let pageActive = true;
    let timer: number | null = null;
    let requestController: AbortController | null = null;
    let refreshFailures = 0;
    let retryAfter: number | null = null;

    function safePageUrl(value: string | null) {
        if (!value) return null;
        const url = new URL(value, endpoint);
        return url.origin === endpoint.origin && url.pathname === endpointPath ? url.href : null;
    }

    function redraw(now = Date.now()) {
        create.disabled = mutationPending || active;
        createLabel.textContent = mutationPending ? 'Requesting export…' : 'Generate export';
        create.setAttribute('aria-busy', String(mutationPending));
        const focused = renderExportHistory(history, jobs, {
            endpoint: endpointPath,
            busy: mutationPending || active,
            linkedJob,
            focusId: focusLinkedExport ? linkedId : null,
            now,
        });
        if (focused) focusLinkedExport = false;
        previous.hidden = !previousUrl;
        next.hidden = !nextUrl;
        previous.disabled = mutationPending;
        next.disabled = mutationPending;
    }

    function stopPolling() {
        window.clearTimeout(timer as number | undefined);
        timer = null;
    }

    function resetRefreshFailures({ clearMessage = false } = {}) {
        if (clearMessage) message.textContent = '';
        refreshFailures = 0;
        retryAfter = null;
    }

    function recordRefreshFailure(errorMessage: string) {
        refreshFailures += 1;
        retryAfter = Date.now() + Math.min(
            MAX_RETRY_DELAY_MS, POLL_INTERVAL_MS * 2 ** (refreshFailures - 1),
        );
        const exhausted = refreshFailures >= MAX_REFRESH_FAILURES;
        active = !exhausted || mergeExportJobs(jobs, linkedJob).some(job => ACTIVE_STATES.has(job.state));
        message.textContent = exhausted
            ? 'Unable to refresh exports after several attempts. Reload this page or try again.'
            : errorMessage;
    }

    function schedule() {
        stopPolling();
        const now = Date.now();
        redraw(now);
        if (!mutationPending && pageActive && !document.hidden) {
            const visibleJobs = mergeExportJobs(jobs, linkedJob, now);
            const exhausted = refreshFailures >= MAX_REFRESH_FAILURES;
            let delay = exportRefreshDelay(visibleJobs, refreshFailures ? false : active, now);
            if (refreshFailures && !exhausted) {
                delay = Math.min(delay ?? Infinity, Math.max(1, retryAfter! - now));
            }
            if (delay !== null) {
                timer = window.setTimeout(() => {
                    // Remove newly expired cards before waiting for the network.
                    redraw();
                    if (exhausted || (refreshFailures && Date.now() < retryAfter!)) {
                        schedule();
                        return;
                    }
                    void refresh();
                }, delay);
            }
        }
    }

    async function refresh() {
        if (!pageActive || document.hidden || refreshFailures >= MAX_REFRESH_FAILURES) return;
        stopPolling();
        requestController?.abort();
        const controller = new AbortController();
        requestController = controller;
        history.setAttribute('aria-busy', 'true');
        try {
            const options: RequestInit = { credentials: 'same-origin', signal: controller.signal };
            const [pageResult, linkedResult] = await Promise.allSettled([
                loadExportPage(currentUrl, endpoint.href, options),
                linkedId ? fetchExportData<ExportJob>(`${endpoint.href}${linkedId}/`, options) : Promise.resolve(null),
            ]);
            if (controller.signal.aborted) return;
            if (refreshFailures) message.textContent = '';
            let failedLoad = false;
            if (pageResult.status === 'fulfilled') {
                const { url, data } = pageResult.value;
                currentUrl = url;
                jobs = data.results;
                previousUrl = safePageUrl(data.previous);
                nextUrl = safePageUrl(data.next);
            } else {
                message.textContent = (pageResult.reason as ExportRequestFailure).message;
                failedLoad = true;
            }
            if (linkedResult.status === 'fulfilled') {
                linkedJob = linkedResult.value;
            } else {
                linkedJob = null;
                message.textContent = (linkedResult.reason as ExportRequestFailure).status! === 404
                    ? 'This export could not be found.'
                    : (linkedResult.reason as ExportRequestFailure).message;
                if ([403, 404].includes((linkedResult.reason as ExportRequestFailure).status!)) {
                    // Missing or inaccessible links cannot recover by polling.
                    linkedId = null;
                    focusLinkedExport = false;
                } else {
                    failedLoad = true;
                }
            }
            const visibleJobs = mergeExportJobs(jobs, linkedJob);
            if (linkedJob && !visibleJobs.some(job => String(job.id).toLowerCase() === linkedId!.toLowerCase())) {
                message.textContent = 'This export has expired. Generate a new export.';
            }
            if (failedLoad) recordRefreshFailure(message.textContent);
            else {
                resetRefreshFailures();
                active = visibleJobs.some(job => ACTIVE_STATES.has(job.state));
            }
        } catch (error) {
            if (!controller.signal.aborted) recordRefreshFailure((error as Error).message);
        } finally {
            if (requestController === controller) {
                requestController = null;
                history.setAttribute('aria-busy', 'false');
                schedule();
            }
        }
    }

    async function submit(url: string) {
        if (mutationPending) return;
        mutationPending = true;
        resetRefreshFailures({ clearMessage: true });
        requestController?.abort();
        const controller = new AbortController();
        requestController = controller;
        stopPolling();
        redraw();
        try {
            const requested = await fetchExportData<ExportJob>(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': csrfToken, 'Accept': 'application/json' },
                signal: controller.signal,
            });
            if (UUID_PATTERN.test(requested.id)) {
                linkedId = requested.id;
                linkedJob = requested;
                focusLinkedExport = true;
                const pageUrl = new URL(window.location.href);
                pageUrl.searchParams.set('export', linkedId);
                window.history.replaceState(null, '', pageUrl);
            }
            message.textContent = 'Your export is queued. We will email you when it is ready.';
            currentUrl = endpoint.href;
        } catch (error) {
            if (!controller.signal.aborted) message.textContent = (error as Error).message;
        } finally {
            if (requestController === controller) requestController = null;
            mutationPending = false;
            await refresh();
        }
    }

    function onSubmit(event: Event) {
        event.preventDefault();
        if (!active) void submit(endpoint.href);
    }
    function onRetry(event: MouseEvent) {
        const button = event.target instanceof Element ? event.target.closest<HTMLButtonElement>('[data-export-retry]') : null;
        if (button && !button.disabled && UUID_PATTERN.test(button.dataset.exportRetry!)) {
            void submit(`${endpointPath}${button.dataset.exportRetry}/retry/`);
        }
    }
    function onPrevious() {
        if (previousUrl) { resetRefreshFailures({ clearMessage: true }); currentUrl = previousUrl; void refresh(); }
    }
    function onNext() {
        if (nextUrl) { resetRefreshFailures({ clearMessage: true }); currentUrl = nextUrl; void refresh(); }
    }
    function onVisibility() {
        stopPolling();
        if (!document.hidden) {
            if (refreshFailures) schedule();
            else void refresh();
        }
    }
    function onPageHide() {
        pageActive = false;
        stopPolling();
        requestController?.abort();
    }
    function onPageShow() {
        pageActive = true;
        onVisibility();
    }
    form.addEventListener('submit', onSubmit);
    history.addEventListener('click', onRetry);
    previous.addEventListener('click', onPrevious);
    next.addEventListener('click', onNext);
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pagehide', onPageHide);
    window.addEventListener('pageshow', onPageShow);
    await refresh();
}
