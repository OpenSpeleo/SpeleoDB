import { configureRuntimeContext, getRuntimeContext } from './runtime_context.js';

describe('map runtime context', () => {
    it('copies and freezes structured Django context without a window bridge', () => {
        const source = { csrfToken: 'token', icons: { sensor: '/sensor.svg' } };
        const context = configureRuntimeContext(source);
        source.icons.sensor = '/changed.svg';

        expect(context).toBe(getRuntimeContext());
        expect(context.icons.sensor).toBe('/sensor.svg');
        expect(Object.isFrozen(context)).toBe(true);
        expect(Object.isFrozen(context.icons)).toBe(true);
        expect(window.MAPVIEWER_CONTEXT).toBeUndefined();
    });
});
