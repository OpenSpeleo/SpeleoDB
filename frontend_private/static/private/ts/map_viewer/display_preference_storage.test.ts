import { flushPreferenceWrites, schedulePreferenceWrite } from './display_preference_storage.ts';

beforeEach(() => {
    flushPreferenceWrites();
    localStorage.clear();
    vi.useFakeTimers();
});
afterEach(() => {
    flushPreferenceWrites();
    vi.useRealTimers();
    vi.restoreAllMocks();
});

it('coalesces a burst and reads the latest value after giving controls a paint opportunity', async () => {
    const write = vi.spyOn(localStorage, 'setItem');
    const preferences = { visible: false };
    schedulePreferenceWrite('display', () => ({ visible: true }));
    schedulePreferenceWrite('display', () => preferences);
    expect(write).not.toHaveBeenCalled();
    preferences.visible = true;
    await vi.runAllTimersAsync();
    expect(write).toHaveBeenCalledExactlyOnceWith('display', '{"visible":true}');
});

it('flushes pending values on pagehide and cancels the scheduled duplicate', async () => {
    const write = vi.spyOn(localStorage, 'setItem');
    schedulePreferenceWrite('display', () => ({ visible: false }));
    window.dispatchEvent(new Event('pagehide'));
    expect(write).toHaveBeenCalledExactlyOnceWith('display', '{"visible":false}');
    await vi.runAllTimersAsync();
    expect(write).toHaveBeenCalledTimes(1);
});

it('flushes one lifecycle owner without discarding another pending record', async () => {
    schedulePreferenceWrite('display', () => ({ color: 'depth' }));
    schedulePreferenceWrite('countries', () => ({ Mexico: false }));
    flushPreferenceWrites('display');
    expect(localStorage.getItem('display')).toBe('{"color":"depth"}');
    expect(localStorage.getItem('countries')).toBeNull();
    await vi.runAllTimersAsync();
    expect(localStorage.getItem('countries')).toBe('{"Mexico":false}');
});

it('reports storage failures without rejecting or retaining failed work', async () => {
    const error = new Error('quota');
    const write = vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw error; });
    const onResult = vi.fn();
    schedulePreferenceWrite('display', () => ({}), onResult);
    await vi.runAllTimersAsync();
    expect(onResult).toHaveBeenCalledExactlyOnceWith(error);
    flushPreferenceWrites();
    expect(write).toHaveBeenCalledTimes(1);
});

it('uses a timer without requesting a frame while the document is hidden', async () => {
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
    const frame = vi.spyOn(window, 'requestAnimationFrame');
    const onResult = vi.fn();
    expect(schedulePreferenceWrite('hidden', () => null, onResult)).toBeUndefined();
    expect(frame).not.toHaveBeenCalled();
    expect(localStorage.getItem('hidden')).toBeNull();
    await vi.runAllTimersAsync();
    expect(localStorage.getItem('hidden')).toBe('null');
    expect(onResult).toHaveBeenCalledExactlyOnceWith(null);
});

it('preserves synchronous reader failures and reports success-callback failures through the same callback', () => {
    const failure = new Error('callback');
    const onResult = vi.fn().mockImplementationOnce(() => { throw failure; });
    schedulePreferenceWrite('callback', () => false, onResult);
    flushPreferenceWrites('callback');
    expect(onResult.mock.calls).toEqual([[null], [failure]]);
    const readerFailure = new Error('reader');
    const readerResult = vi.fn();
    schedulePreferenceWrite('reader', () => { throw readerFailure; }, readerResult);
    flushPreferenceWrites('reader');
    expect(readerResult).toHaveBeenCalledExactlyOnceWith(readerFailure);
    expect(localStorage.getItem('reader')).toBeNull();
});
