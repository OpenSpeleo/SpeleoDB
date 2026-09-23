import { createViewerUpdateScheduler } from './viewer_updates.js';

function harness() {
    const starts = [];
    let clock = 0;
    const cancel = vi.fn();
    const yieldWork = vi.fn(async () => { clock = 0; });
    const scheduler = createViewerUpdateScheduler({
        scheduleAfterPaint: callback => {
            const entry = { callback, cancelled: false };
            starts.push(entry);
            return () => { entry.cancelled = true; cancel(); };
        },
        now: () => clock,
        budget: () => 8,
        yieldWork,
    });
    return { scheduler, start: () => {
        for (const entry of starts.splice(0)) if (!entry.cancelled) entry.callback();
    }, cancel, yieldWork, advance: () => { clock += 9; } };
}

it('does no map work before the paint boundary and coalesces the same key', async () => {
    const h = harness();
    const old = vi.fn();
    const latest = vi.fn();
    const first = h.scheduler.schedule('visibility', old);
    const second = h.scheduler.schedule('visibility', latest);
    expect(old).not.toHaveBeenCalled();
    expect(latest).not.toHaveBeenCalled();
    expect(await first).toEqual({ status: 'superseded' });
    h.start();
    expect(await second).toEqual({ status: 'applied' });
    expect(old).not.toHaveBeenCalled();
    expect(latest).toHaveBeenCalledOnce();
    await h.scheduler.whenIdle();
});

it('lets a newer intent invalidate already-running work at its next yield', async () => {
    const h = harness();
    let release;
    const held = new Promise(resolve => { release = resolve; });
    const staleApply = vi.fn();
    const first = h.scheduler.schedule('color', async context => {
        await held;
        if (context.isCurrent()) staleApply();
    });
    h.start();
    await Promise.resolve();
    const latest = vi.fn();
    const second = h.scheduler.schedule('color', latest);
    release();
    expect(await first).toEqual({ status: 'superseded' });
    await Promise.resolve();
    expect(latest).not.toHaveBeenCalled();
    h.start();
    expect(await second).toEqual({ status: 'applied' });
    expect(staleApply).not.toHaveBeenCalled();
});

it('waits through two frames before the default scheduler applies map work', async () => {
    vi.useFakeTimers();
    const frames = [];
    vi.stubGlobal('requestAnimationFrame', callback => { frames.push(callback); return frames.length; });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    try {
        const scheduler = createViewerUpdateScheduler();
        const work = vi.fn();
        const applied = scheduler.schedule('display', work);
        frames.shift()();
        await vi.runAllTimersAsync();
        expect(work).not.toHaveBeenCalled();
        frames.shift()();
        expect(work).not.toHaveBeenCalled();
        await vi.runAllTimersAsync();
        expect(await applied).toEqual({ status: 'applied' });
        expect(work).toHaveBeenCalledOnce();
    } finally {
        vi.unstubAllGlobals();
        vi.useRealTimers();
    }
});

it('gives input arriving after an earlier job\'s frames its own paint boundary', async () => {
    vi.useFakeTimers();
    const frames = new Map();
    let id = 0;
    vi.stubGlobal('requestAnimationFrame', callback => { frames.set(++id, callback); return id; });
    vi.stubGlobal('cancelAnimationFrame', frame => frames.delete(frame));
    const frame = () => {
        const callbacks = [...frames.values()]; frames.clear();
        for (const callback of callbacks) callback();
    };
    try {
        const scheduler = createViewerUpdateScheduler();
        const first = scheduler.schedule('first', vi.fn());
        frame(); frame();
        const work = vi.fn();
        const second = scheduler.schedule('later-input', work);
        await vi.runAllTimersAsync();
        expect(await first).toEqual({ status: 'applied' });
        expect(work).not.toHaveBeenCalled();
        frame();
        await vi.runAllTimersAsync();
        expect(work).not.toHaveBeenCalled();
        frame();
        await vi.runAllTimersAsync();
        expect(await second).toEqual({ status: 'applied' });
        expect(work).toHaveBeenCalledOnce();
    } finally {
        vi.unstubAllGlobals();
        vi.useRealTimers();
    }
});

it.each([0, 1, 2])('cancels default scheduled work after %i frames and releases idle', async frameCount => {
    vi.useFakeTimers();
    const frames = new Map();
    let id = 0;
    vi.stubGlobal('requestAnimationFrame', callback => { frames.set(++id, callback); return id; });
    vi.stubGlobal('cancelAnimationFrame', frame => frames.delete(frame));
    try {
        const scheduler = createViewerUpdateScheduler();
        const work = vi.fn();
        const applied = scheduler.schedule('display', work);
        for (let index = 0; index < frameCount; index++) {
            const callbacks = [...frames.values()]; frames.clear();
            for (const callback of callbacks) callback();
        }
        const idle = scheduler.whenIdle();
        scheduler.cancel('display');
        await idle;
        await vi.runAllTimersAsync();
        expect(await applied).toEqual({ status: 'cancelled' });
        expect(work).not.toHaveBeenCalled();
        expect(frames.size).toBe(0);
        expect(vi.getTimerCount()).toBe(0);
    } finally {
        vi.unstubAllGlobals();
        vi.useRealTimers();
    }
});

it('releases a cancelled paint gate while another job is already active', async () => {
    const h = harness();
    let release;
    const held = new Promise(resolve => { release = resolve; });
    const first = h.scheduler.schedule('first', () => held);
    h.start();
    await Promise.resolve();
    const work = vi.fn();
    const second = h.scheduler.schedule('second', work);
    const idle = h.scheduler.whenIdle();
    h.scheduler.cancelAll();
    release();
    expect(await first).toEqual({ status: 'cancelled' });
    expect(await second).toEqual({ status: 'cancelled' });
    await idle;
    expect(work).not.toHaveBeenCalled();
    expect(h.cancel).toHaveBeenCalledOnce();
});

it('yields between independent application jobs when the work budget is spent', async () => {
    const h = harness();
    const first = h.scheduler.schedule('a', () => h.advance());
    const second = h.scheduler.schedule('b', vi.fn());
    h.start();
    await Promise.all([first, second]);
    expect(h.yieldWork).toHaveBeenCalledOnce();
});

it('contains failures and continues unrelated work', async () => {
    const h = harness();
    const error = new Error('map removed');
    const onError = vi.fn();
    const failed = h.scheduler.schedule('a', () => { throw error; }, { onError });
    const successful = h.scheduler.schedule('b', vi.fn());
    h.start();
    expect(await failed).toEqual({ status: 'failed', error });
    expect(await successful).toEqual({ status: 'applied' });
    expect(onError).toHaveBeenCalledWith(error);
});

it('cancels queued work and releases idle waiters on teardown', async () => {
    const h = harness();
    const work = vi.fn();
    const pending = h.scheduler.schedule('a', work);
    const idle = h.scheduler.whenIdle();
    h.scheduler.cancelAll();
    expect(await pending).toEqual({ status: 'cancelled' });
    await idle;
    expect(work).not.toHaveBeenCalled();
    expect(h.cancel).toHaveBeenCalledOnce();
});
