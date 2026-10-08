import type { ViewerPaintGate, ViewerUpdateJob, ViewerUpdateResult, ViewerUpdateScheduler, ViewerUpdateStatus, ViewerSchedulerOptions } from '../../../../../ts-types/domain/viewer-updates.ts';
import { DEFAULTS } from './config.ts';

/** A future task, rather than a resolved promise, gives input a turn. */
export function yieldViewerWork() {
    if (typeof globalThis.scheduler?.yield === 'function') return globalThis.scheduler.yield();
    return new Promise<void>(resolve => setTimeout(resolve, 0));
}

/** Allow an intervening rendering opportunity before scheduling map work. */
function afterPaint(callback: () => void) {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let frame = requestAnimationFrame(() => {
        frame = requestAnimationFrame(() => { timer = setTimeout(callback, 0); });
    });
    return () => {
        cancelAnimationFrame(frame);
        clearTimeout(timer);
    };
}

/** Keyed, serial map application. Network requests must run outside this queue. */
export function createViewerUpdateScheduler({
    scheduleAfterPaint = afterPaint,
    yieldWork = yieldViewerWork,
    now = () => performance.now(),
    budget = () => DEFAULTS.VIEWER_WORK.BUDGET_MS,
} : ViewerSchedulerOptions = {}): ViewerUpdateScheduler {
    const pending = new Map<string | object, ViewerUpdateJob>();
    const current = new Map<string | object, ViewerUpdateJob>();
    const idle = new Set<() => void>();
    let active: ViewerUpdateJob | null = null;
    let running = false;

    function nextPaint() {
        // The following assignments finish the existing synchronous gate construction.
        const gate = { ready: false } as ViewerPaintGate;
        gate.promise = new Promise<void>(resolve => { gate.release = resolve; });
        gate.cancel = scheduleAfterPaint(() => {
            gate.ready = true;
            gate.cancel = null;
            gate.release();
        });
        return gate;
    }

    function settle(job: ViewerUpdateJob, status: ViewerUpdateStatus, error?: unknown) {
        if (job.settled) return;
        job.settled = true;
        job.paint.cancel?.();
        job.paint.cancel = null;
        job.paint.release();
        job.resolve(error ? { status, error } : { status });
        if (current.get(job.key) === job) current.delete(job.key);
    }

    function finishIdle() {
        if (running || pending.size) return;
        for (const resolve of idle) resolve();
        idle.clear();
    }

    async function run() {
        running = true;
        let sliceStarted = now();
        try {
            while (pending.size) {
                const [key, job] = pending.entries().next().value!;
                pending.delete(key);
                active = job;
                const isCurrent = () => !job.settled && current.get(key) === job;
                const paintReady = job.paint.ready;
                await job.paint.promise;
                if (!isCurrent()) continue;
                if (!paintReady) sliceStarted = now();
                const context = {
                    isCurrent,
                    async yield() {
                        await yieldWork();
                        sliceStarted = now();
                        return isCurrent();
                    },
                    shouldYield: () => now() - sliceStarted >= budget(),
                };
                try {
                    await job.work(context);
                    settle(job, isCurrent() ? 'applied' : 'superseded');
                } catch (error) {
                    if (isCurrent()) {
                        settle(job, 'failed', error);
                        try { job.onError?.(error); } catch { /* Error reporting must not stop unrelated work. */ }
                    } else {
                        settle(job, 'superseded');
                    }
                }
                active = null;
                if (pending.size && now() - sliceStarted >= budget()) {
                    await yieldWork();
                    sliceStarted = now();
                }
            }
        } finally {
            active = null;
            running = false;
            finishIdle();
        }
    }

    return {
        schedule(key, work, { onError } = {}) {
            const previous = current.get(key);
            if (previous) settle(previous, 'superseded');
            const promise = new Promise<ViewerUpdateResult>(resolve => {
                const job = { key, work, onError, resolve, settled: false, paint: nextPaint() };
                current.set(key, job);
                pending.set(key, job);
            });
            if (!running) void run();
            return promise;
        },
        cancel(key) {
            const job = current.get(key);
            if (job) settle(job, 'cancelled');
            pending.delete(key);
            finishIdle();
        },
        cancelAll() {
            for (const job of current.values()) settle(job, 'cancelled');
            if (active) settle(active, 'cancelled');
            pending.clear();
            finishIdle();
        },
        whenIdle() {
            if (!running && !pending.size) return Promise.resolve();
            return new Promise<void>(resolve => idle.add(resolve));
        },
    };
}

export const ViewerUpdates = createViewerUpdateScheduler();
