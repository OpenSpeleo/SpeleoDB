import { configureRuntimeContext, getRuntimeContext } from './runtime_context.ts';

afterEach(() => { configureRuntimeContext({}); });

describe('map runtime context', () => {
    it('copies and freezes structured Django context without a window bridge', () => {
        const source = { csrfToken: 'token', icons: { sensor: '/sensor.svg' } };
        const context = configureRuntimeContext(source);
        source.icons.sensor = '/changed.svg';

        expect(context).toBe(getRuntimeContext());
        expect(context.icons.sensor).toBe('/sensor.svg');
        expect(Object.isFrozen(context)).toBe(true);
        expect(Object.isFrozen(context.icons)).toBe(true);
        expect((window as Window & { MAPVIEWER_CONTEXT?: unknown }).MAPVIEWER_CONTEXT).toBeUndefined();
    });
});

it.each([null, undefined, false, 1, 'context'])('normalizes non-object context %s and replaces the stored identity', value => {
    const previous = getRuntimeContext();
    const current = configureRuntimeContext(value);
    expect(current).toEqual({ icons: {} });
    expect(current).not.toBe(previous);
    expect(current).toBe(getRuntimeContext());
});

it('copies only the outer object and icons while retaining other nested identities', () => {
    const geometryColors = ['red'];
    const icons = { sensor: '/sensor.svg' };
    const source = { geometryColors, icons };
    const result = configureRuntimeContext(source);
    expect(result).not.toBe(source);
    expect(result.icons).not.toBe(icons);
    expect(result.geometryColors).toBe(geometryColors);
    geometryColors.push('blue');
    expect(result.geometryColors).toEqual(['red', 'blue']);
});
