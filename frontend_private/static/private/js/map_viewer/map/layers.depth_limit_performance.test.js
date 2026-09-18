import { Config } from '../config.js';
import { State, createDefaultDisplayPreferences } from '../state.js';
import { Geometry } from './geometry.js';
import { Layers } from './layers.js';

it('changes depth settings and visibility using cached domains after ingesting 20,000 survey lines', async () => {
    State.resetLayerState();
    State.displayPreferences = createDefaultDisplayPreferences();
    localStorage.clear();
    const previousProjects = Config._projects;
    const sources = new Map();
    const definitions = new Map();
    const setData = vi.fn();
    const map = {
        getStyle: () => ({}),
        getSource: vi.fn(id => sources.get(id)),
        addSource: vi.fn((id, source) => sources.set(id, { ...source, setData })),
        getLayer: id => definitions.get(id),
        addLayer: vi.fn(layer => definitions.set(layer.id, layer)),
        setPaintProperty: vi.fn(),
        setLayoutProperty: vi.fn(),
        setFilter: vi.fn(),
    };
    State.map = map;
    const projects = Array.from({ length: 20 }, (_, projectIndex) => ({
        id: `depth-performance-${projectIndex}`, color: '#123456',
    }));
    Config._projects = projects;
    const input = new Map(projects.map((project, projectIndex) => [project.id, {
        type: 'FeatureCollection',
        features: Array.from({ length: 1000 }, (_, index) => ({
            type: 'Feature',
            properties: { depth: projectIndex * 1000 + index + 1 },
            geometry: { type: 'LineString', coordinates: [[-87, 20], [-87.01, 20.01]] },
        })),
    }]));
    const download = vi.fn(async projectId => ({ ok: true, json: async () => input.get(projectId) }));
    vi.stubGlobal('fetch', download);
    vi.stubGlobal('mapboxgl', {
        LngLatBounds: class {
            extend() { return this; }
            isEmpty() { return false; }
        },
    });
    // Keep the real preprocessing and snap-cache work in the ingest path.
    const cache = vi.spyOn(Geometry, 'cacheLineFeatures');
    const snapshots = [];
    const restore = [];
    const forbidRead = () => { throw new Error('Depth controls must not read survey feature data'); };

    try {
        for (const project of projects) await Layers.addProjectGeoJSON(project.id, project.id);
        expect(download).toHaveBeenCalledTimes(20);
        expect(cache).toHaveBeenCalledTimes(20);
        expect(map.addSource).toHaveBeenCalledTimes(20);
        expect(map.addLayer).toHaveBeenCalledTimes(60);
        expect(State.projectDepthDomains.size).toBe(20);
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 20000 });
        const cachedDomains = [...State.projectDepthDomains];
        cachedDomains.forEach(([, domain]) => Object.freeze(domain));

        for (const project of projects) {
            const source = sources.get(`project-geojson-${project.id}`);
            const data = source.data;
            for (const collection of [input.get(project.id), data]) {
                snapshots.push([collection, JSON.stringify(collection)]);
                const features = collection.features;
                Object.defineProperty(collection, 'features', { configurable: true, get: forbidRead });
                restore.push(() => Object.defineProperty(collection, 'features', { configurable: true, writable: true, value: features }));
            }
            Object.defineProperty(source, 'data', { configurable: true, get: forbidRead });
            restore.push(() => Object.defineProperty(source, 'data', { configurable: true, writable: true, value: data }));
        }
        map.getSource.mockClear();
        map.getSource.mockImplementation(forbidRead);

        Layers.setColorMode('depth');
        for (let index = 0; index < 100; index += 1) {
            const limit = 50 + index;
            Layers.setDepthLimit(limit, 'ft');
            Layers.setDepthLimit(limit, 'm');
            const project = projects[index % projects.length];
            Layers.toggleProjectVisibility(project.id, Math.floor(index / projects.length) % 2 === 1);
            expect(State.activeDepthDomain).toEqual(Layers.getVisibleProjectIds().length ? { min: 0, max: limit } : null);
        }
        Layers.toggleProjectVisibility(projects.at(-1).id, true);
        Layers.setDepthLimit(null, 'ft');
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 20000 });
        expect(download).toHaveBeenCalledTimes(20);
        expect(cache).toHaveBeenCalledTimes(20);
        expect(map.addSource).toHaveBeenCalledTimes(20);
        expect(map.addLayer).toHaveBeenCalledTimes(60);
        expect(map.getSource).not.toHaveBeenCalled();
        expect(setData).not.toHaveBeenCalled();
        expect(map.setPaintProperty).toHaveBeenCalled();
        expect([...State.projectDepthDomains]).toEqual(cachedDomains);
        for (const [id, domain] of cachedDomains) expect(State.projectDepthDomains.get(id)).toBe(domain);

        restore.splice(0).forEach(restoreProperty => restoreProperty());
        for (const [collection, snapshot] of snapshots) expect(JSON.stringify(collection)).toBe(snapshot);
    } finally {
        restore.forEach(restoreProperty => restoreProperty());
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        State.map = null;
        State.resetLayerState();
        State.displayPreferences = createDefaultDisplayPreferences();
        Config._projects = previousProjects;
        localStorage.clear();
    }
});
