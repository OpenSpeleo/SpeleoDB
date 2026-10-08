import { MAP_ICON_URLS } from '@speleodb/map-viewer/icons';
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
    expect(Object.values(current.icons)).toHaveLength(7);
    expect(Object.values(current.icons)).toEqual(expect.arrayContaining(Object.values(MAP_ICON_URLS)));
    expect(current).not.toBe(previous);
    expect(current).toBe(getRuntimeContext());
});

it('supplies shared icons to menus and dialogs when Django omits the former asset context', () => {
    const { icons } = configureRuntimeContext({ csrfToken: 'token' });
    expect(icons).toEqual({
        sensor: MAP_ICON_URLS.sensor, biology: MAP_ICON_URLS.biology,
        bone: MAP_ICON_URLS.bones, artifact: MAP_ICON_URLS.artifact,
        geology: MAP_ICON_URLS.geology, explorationLead: MAP_ICON_URLS.explorationLead,
        cylinderOrange: MAP_ICON_URLS.cylinder,
    });
});

it('retains valid icon overrides and fills omitted or unusable values without mutating the input', () => {
    const source = { icons: { sensor: '/custom.svg', biology: undefined, bone: null, artifact: '', geology: ' ' } };
    const { icons } = configureRuntimeContext(source);
    expect(icons.sensor).toBe('/custom.svg');
    expect(icons.biology).toBe(MAP_ICON_URLS.biology);
    expect(icons.bone).toBe(MAP_ICON_URLS.bones);
    expect(icons.artifact).toBe(MAP_ICON_URLS.artifact);
    expect(icons.geology).toBe(MAP_ICON_URLS.geology);
    expect(source.icons.bone).toBeNull();
    expect(source.icons.artifact).toBe('');
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
