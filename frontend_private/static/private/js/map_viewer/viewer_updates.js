import { DEFAULTS } from './config.js';

/** A future task, rather than a resolved promise, gives input a turn. */
export function yieldViewerWork() {
    if (typeof globalThis.scheduler?.yield === 'function') return globalThis.scheduler.yield();
    return new Promise(resolve => setTimeout(resolve, 0));
}

/** Allow an intervening rendering opportunity before scheduling map work. */
function afterPaint(callback) {
    let timer;
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
} = {}) {
    const pending = new Map();
    const current = new Map();
    const idle = new Set();
    let active = null;
    let running = false;

    function nextPaint() {
        const gate = { ready: false };
        gate.promise = new Promise(resolve => { gate.release = resolve; });
        gate.cancel = scheduleAfterPaint(() => {
            gate.ready = true;
            gate.cancel = null;
            gate.release();
        });
        return gate;
    }

    function settle(job, status, error) {
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
                const [key, job] = pending.entries().next().value;
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
            const promise = new Promise(resolve => {
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
            return new Promise(resolve => idle.add(resolve));
        },
    };
}

export const ViewerUpdates = createViewerUpdateScheduler();
