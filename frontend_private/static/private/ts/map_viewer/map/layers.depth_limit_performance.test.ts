import { startApiServer } from '../../../../../../frontend_common/test/api-server.ts';
import type { FeatureCollection, Geometry as GeoJSONGeometry } from 'geojson';
import type { Mock } from 'vitest';
import type { JSONObject } from '../../../../../../ts-types/domain/json.ts';
import type { RendererLayer } from '../../../../../../ts-types/domain/renderer.ts';
type Collection = FeatureCollection<GeoJSONGeometry, JSONObject>;
interface Source { data: Collection; setData: Mock }
import { Config } from '../config.ts';
import { State, createDefaultDisplayPreferences } from '../state.ts';
import { Geometry } from './geometry.ts';
import { Layers } from './layers.ts';

it('changes depth settings and visibility using cached domains without rereading survey data', async () => {
    // Exercise real frame scheduling while checking cached-data work counts.
    State.resetLayerState();
    State.displayPreferences = createDefaultDisplayPreferences();
    localStorage.clear();
    const previousProjects = Config._projects;
    const sources = new Map<string, Source>();
    const definitions = new Map<string, RendererLayer>();
    const setData = vi.fn();
    const map = {
        getStyle: () => ({}),
        getSource: vi.fn((id: string) => sources.get(id)),
        addSource: vi.fn((id: string, source: { data: Collection }) => sources.set(id, { ...source, setData })),
        getLayer: (id: string) => definitions.get(id),
        addLayer: vi.fn((layer: RendererLayer) => definitions.set(layer.id, layer)),
        setPaintProperty: vi.fn(),
        setLayoutProperty: vi.fn(),
        setFilter: vi.fn(),
    };
    State.map = (map) as unknown as NonNullable<typeof State.map>;
    const projects = Array.from({ length: 2 }, (_, projectIndex) => ({
        id: `depth-performance-${projectIndex}`, color: '#123456',
    }));
    Config._projects = projects;
    const input = new Map<string, Collection>(projects.map((project, projectIndex) => [project.id, {
        type: 'FeatureCollection',
        features: Array.from({ length: 3 }, (_, index) => ({
            type: 'Feature',
            properties: { depth: projectIndex * 3 + index + 1 },
            geometry: { type: 'LineString', coordinates: [[-87, 20], [-87.01, 20.01]] },
        })),
    }]));
    const server = await startApiServer();
    server.handle(request => ({ json: input.get(request.path.slice(1)) }));
    // The test environment cannot create native WebGL bounds.
    vi.stubGlobal('__mapRenderer', {
        LngLatBounds: class {
            extend() { return this; }
            isEmpty() { return false; }
        },
    });
    // Keep the real preprocessing and snap-cache work in the ingest path.
    const snapshots: Array<[Collection, string]> = [];
    const restore: Array<() => unknown> = [];
    const forbidRead = () => { throw new Error('Depth controls must not read survey feature data'); };

    try {
        for (const project of projects) await Layers.addProjectGeoJSON(project.id, `${server.origin}/${project.id}`);
        expect(server.requests).toHaveLength(2);
        expect(map.addSource).toHaveBeenCalledTimes(2);
        expect(map.addLayer).toHaveBeenCalledTimes(6);
        expect(State.projectDepthDomains.size).toBe(2);
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 6 });
        const cachedDomains = [...State.projectDepthDomains];
        const cachedSnapPoints = Geometry.getSnapInfo().totalSnapPoints;
        cachedDomains.forEach(([, domain]) => Object.freeze(domain));

        for (const project of projects) {
            const source = sources.get(`project-geojson-${project.id}`)!;
            const data = source.data;
            for (const collection of [input.get(project.id)!, data]) {
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

        await Layers.setColorMode('depth');
        for (let index = 0; index < 3; index += 1) {
            const limit = 1 + index;
            Layers.setDepthLimit(limit, 'ft');
            await Layers.whenDisplayApplied();
            Layers.setDepthLimit(limit, 'm');
            await Layers.whenDisplayApplied();
            const project = projects[index % projects.length]!;
            await Layers.toggleProjectVisibility(project.id, Math.floor(index / projects.length) % 2 === 1);
            expect(State.activeDepthDomain).toEqual(Layers.getVisibleProjectIds().length ? { min: 0, max: limit } : null);
        }
        await Layers.toggleProjectVisibility(projects.at(-1)!.id, true);
        Layers.setDepthLimit(null, 'ft');
        await Layers.whenDisplayApplied();
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 6 });
        expect(server.requests).toHaveLength(2);
        expect(map.addSource).toHaveBeenCalledTimes(2);
        expect(map.addLayer).toHaveBeenCalledTimes(6);
        expect(map.getSource).not.toHaveBeenCalled();
        expect(setData).not.toHaveBeenCalled();
        expect(Geometry.getSnapInfo().totalSnapPoints).toBe(cachedSnapPoints);
        expect(map.setPaintProperty).toHaveBeenCalled();
        expect([...State.projectDepthDomains]).toEqual(cachedDomains);
        for (const [id, domain] of cachedDomains) expect(State.projectDepthDomains.get(id)).toBe(domain);

        restore.splice(0).forEach(restoreProperty => restoreProperty());
        for (const [collection, snapshot] of snapshots) expect(JSON.stringify(collection)).toBe(snapshot);
    } finally {
        restore.forEach(restoreProperty => restoreProperty());
        vi.unstubAllGlobals();
        State.map = null;
        State.resetLayerState();
        State.displayPreferences = createDefaultDisplayPreferences();
        Config._projects = previousProjects;
        await server.close();
        localStorage.clear();
    }
});
