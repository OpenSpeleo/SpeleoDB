import { Config } from '../config.js';
import { State } from '../state.js';
import { Layers } from './layers.js';

function createStorageMock() {
    const store = new Map();
    return {
        getItem: (key) => (store.has(key) ? store.get(key) : null),
        setItem: (key, value) => {
            store.set(String(key), String(value));
        },
        removeItem: (key) => {
            store.delete(String(key));
        },
        clear: () => {
            store.clear();
        }
    };
}

describe('Layers depth domain reactivity', () => {
    beforeEach(() => {
        Object.defineProperty(globalThis, 'localStorage', {
            value: createStorageMock(),
            configurable: true,
            writable: true
        });

        localStorage.clear();
        State.resetLayerState();
        State.map = null;
        Layers.colorMode = 'project';
        Config._projects = [
            { id: '1', name: 'Project A' },
            { id: '2', name: 'Project B' }
        ];
        State.projectDepthDomains.set('1', { min: 0, max: 25 });
        State.projectDepthDomains.set('2', { min: 0, max: 80 });
    });

    it('recalculates merged depth domain when a deeper project is hidden', () => {
        Layers.saveProjectVisibilityPref('1', true);
        Layers.saveProjectVisibilityPref('2', true);
        Layers.recomputeActiveDepthDomain();
        expect(Layers.getActiveDepthDomain()).toEqual({ min: 0, max: 80 });

        Layers.toggleProjectVisibility('2', false);
        expect(Layers.getActiveDepthDomain()).toEqual({ min: 0, max: 25 });
    });

    it('recalculates merged depth domain when a deeper project is shown', () => {
        Layers.saveProjectVisibilityPref('1', true);
        Layers.saveProjectVisibilityPref('2', false);
        Layers.recomputeActiveDepthDomain();
        expect(Layers.getActiveDepthDomain()).toEqual({ min: 0, max: 25 });

        Layers.toggleProjectVisibility('2', true);
        expect(Layers.getActiveDepthDomain()).toEqual({ min: 0, max: 80 });
    });

    it('records effective visibility even when map is null (pre-load country gate)', () => {
        // Simulate: map not ready, country gate hides project
        State.map = null;
        Layers.applyProjectLayerVisibility('1', false);

        // Effective state is recorded despite no map
        expect(State.effectiveProjectVisibility.get('1')).toBe(false);

        // getVisibleProjectIds should exclude it
        Layers.saveProjectVisibilityPref('1', true);
        Layers.saveProjectVisibilityPref('2', true);
        const visible = Layers.getVisibleProjectIds();
        expect(visible).toContain('2');
        expect(visible).not.toContain('1');
    });

    it('applyProjectLayerVisibility without override reads effectiveProjectVisibility', () => {
        State.map = null;
        // Pre-set effective visibility to false (as country gate would)
        State.effectiveProjectVisibility.set('1', false);

        // Call without override — should read the effective state
        Layers.applyProjectLayerVisibility('1');

        expect(State.effectiveProjectVisibility.get('1')).toBe(false);
    });

    it('effective visibility set before map ready is honored by later applyProjectLayerVisibility calls', () => {
        // Simulate the real init sequence:
        // 1. Country gate hides project BEFORE map layers exist
        State.map = null;
        Layers.applyProjectLayerVisibility('1', false);
        expect(State.effectiveProjectVisibility.get('1')).toBe(false);

        // 2. Map becomes ready (simulate addProjectGeoJSON flow)
        State.map = { getStyle: () => ({}), getLayer: () => null, setLayoutProperty: vi.fn() };

        // 3. addProjectGeoJSON calls applyProjectLayerVisibility WITHOUT override
        //    It must read the effective visibility (false), not the individual pref (true)
        Layers.saveProjectVisibilityPref('1', true);
        Layers.applyProjectLayerVisibility('1');

        // The effective state must still be false (country gate)
        expect(State.effectiveProjectVisibility.get('1')).toBe(false);

        // And getVisibleProjectIds must exclude it
        Layers.saveProjectVisibilityPref('2', true);
        const visible = Layers.getVisibleProjectIds();
        expect(visible).not.toContain('1');
        expect(visible).toContain('2');
    });

    it('if effectiveProjectVisibility.set is moved after map guard, this test fails', () => {
        // Regression guard: if someone moves the set() call below the
        // "if (!map) return" guard, this exact scenario breaks.
        State.map = null;

        // With map=null, applyProjectLayerVisibility must still record state
        Layers.applyProjectLayerVisibility('2', false);
        expect(State.effectiveProjectVisibility.has('2')).toBe(true);
        expect(State.effectiveProjectVisibility.get('2')).toBe(false);
    });

    it('toggleProjectVisibility clears effectiveProjectVisibility so fresh pref is used', () => {
        // Simulate: effective was set to false (e.g. country gate hid it)
        State.effectiveProjectVisibility.set('1', false);
        Layers.saveProjectVisibilityPref('1', false);

        // User toggles project ON
        Layers.toggleProjectVisibility('1', true);

        // The stale effective=false must be gone; new effective should be true
        expect(State.effectiveProjectVisibility.get('1')).toBe(true);
        expect(Layers.getVisibleProjectIds()).toContain('1');
    });

    it('toggleProjectVisibility OFF clears effective and re-applies as false', () => {
        State.effectiveProjectVisibility.set('1', true);
        Layers.saveProjectVisibilityPref('1', true);

        Layers.toggleProjectVisibility('1', false);

        expect(State.effectiveProjectVisibility.get('1')).toBe(false);
        expect(Layers.getVisibleProjectIds()).not.toContain('1');
    });

    it('full scenario: country gate OFF at init, then user toggles project ON (country still OFF)', () => {
        // 1. Init: country gate hides project
        State.map = null;
        Layers.saveProjectVisibilityPref('1', true);
        Layers.applyProjectLayerVisibility('1', false);
        expect(State.effectiveProjectVisibility.get('1')).toBe(false);

        // 2. Map becomes ready
        State.map = { getStyle: () => ({}), getLayer: () => null, setLayoutProperty: vi.fn() };

        // 3. User toggles project ON via toggleProjectVisibility
        Layers.toggleProjectVisibility('1', true);

        // 4. effective is now true (stale country gate was cleared by toggle)
        expect(State.effectiveProjectVisibility.get('1')).toBe(true);
        expect(Layers.getVisibleProjectIds()).toContain('1');
    });

    it('full scenario: project OFF at load, country ON, user toggles project ON', () => {
        State.map = { getStyle: () => ({}), getLayer: () => null, setLayoutProperty: vi.fn() };

        // Project individually OFF from previous session
        Layers.saveProjectVisibilityPref('1', false);
        Layers.applyProjectLayerVisibility('1');
        expect(State.effectiveProjectVisibility.get('1')).toBe(false);

        // User toggles project ON
        Layers.toggleProjectVisibility('1', true);

        // Must be visible now
        expect(State.effectiveProjectVisibility.get('1')).toBe(true);
        expect(Layers.getVisibleProjectIds()).toContain('1');
    });

    it('returns null merged domain and unavailable event when all projects are hidden', () => {
        let lastDomainDetail = null;
        const handleDomainUpdate = (event) => {
            lastDomainDetail = event.detail;
        };
        window.addEventListener('speleo:depth-domain-updated', handleDomainUpdate);

        Layers.saveProjectVisibilityPref('1', true);
        Layers.saveProjectVisibilityPref('2', true);
        Layers.recomputeActiveDepthDomain();

        Layers.toggleProjectVisibility('1', false);
        Layers.toggleProjectVisibility('2', false);

        expect(Layers.getActiveDepthDomain()).toBeNull();
        expect(lastDomainDetail).not.toBeNull();
        expect(lastDomainDetail.available).toBe(false);
        expect(lastDomainDetail.domain).toBeNull();

        window.removeEventListener('speleo:depth-domain-updated', handleDomainUpdate);
    });
});

