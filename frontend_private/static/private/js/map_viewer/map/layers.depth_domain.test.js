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
        State.init();
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

