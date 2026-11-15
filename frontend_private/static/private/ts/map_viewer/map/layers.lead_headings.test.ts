import { MAP_LAYER_MIN_ZOOM } from '@speleodb/map-viewer';
import type { FeatureCollection } from 'geojson';
import type { LayerSpecification } from 'maplibre-gl';
import type { ViewerMap } from '../../../../../../ts-types/domain/map-state.ts';
import { Layers } from './layers.ts';
import { State } from '../state.ts';
import { Config } from '../config.ts';
import { getSourceData } from './layers/source_lifecycle.ts';

it.each([true, false])('keeps lead cones aligned through visibility, movement and reload with icon available: %s', (iconAvailable) => {
    // JSDOM has no WebGL context. Only the renderer boundary uses an in-memory source/layer store.
    const sources = new Map<string, { data: FeatureCollection; setData(data: FeatureCollection): void }>();
    const layers = new Map<string, LayerSpecification>();
    State.map = {
        getSource: (id: string) => sources.get(id),
        addSource: (id: string, options: { data: FeatureCollection }) => {
            let data = options.data;
            sources.set(id, { setData(value) { data = value; }, get data() { return data; } });
        },
        getLayer: (id: string) => layers.get(id),
        addLayer: (layer: LayerSpecification) => { layers.set(layer.id, layer); },
        hasImage: () => iconAvailable,
        setFilter: (id: string, filter: never) => { Object.assign(layers.get(id)!, { filter }); },
        setLayoutProperty: (id: string, property: string, value: unknown) => {
            const layer = layers.get(id)!;
            layer.layout = { ...layer.layout, [property]: value };
        },
    } as unknown as ViewerMap;
    State.resetLayerState();
    Config._projects = [{ id: 'project', permissions: 'ADMIN' }];
    State.effectiveProjectVisibility.set('project', true);
    State.explorationLeads.set('lead', {
        id: 'lead', projectId: 'project', coordinates: [6.5, 46.5],
        lineName: 'Survey', description: 'Lead', headings: [0, 90], createdAt: undefined,
    });
    try {
        Layers.refreshExplorationLeadsLayer();
        const cones = () => getSourceData<FeatureCollection>(sources.get('exploration-leads-cones-source'))!;
        expect(cones().features).toHaveLength(2);
        expect(cones().features.every(feature => feature.properties?.project_id === 'project')).toBe(true);
        const coneLayer = layers.get('exploration-leads-cones-layer')!;
        expect(coneLayer.minzoom).toBe(MAP_LAYER_MIN_ZOOM.EXPLORATION_LEAD_SYMBOL);
        expect(layers.get('exploration-leads-layer')).toMatchObject({
            minzoom: MAP_LAYER_MIN_ZOOM.EXPLORATION_LEAD_SYMBOL,
            type: iconAvailable ? 'symbol' : 'circle',
        });
        State.effectiveProjectVisibility.set('project', false);
        Layers.applyProjectScopedMarkerVisibility();
        expect(coneLayer).toHaveProperty('filter', Layers.getProjectScopedMarkerFilter());
        State.displayPreferences.categories.explorationLeads = false;
        Layers.applyCategoryVisibility('explorationLeads');
        expect(coneLayer.layout).toHaveProperty('visibility', 'none');
        State.displayPreferences.categories.explorationLeads = true;
        State.effectiveProjectVisibility.set('project', true);
        Layers.applyProjectScopedMarkerVisibility();
        expect(coneLayer.layout).toHaveProperty('visibility', 'visible');
        const original = structuredClone(cones());
        Layers.updateExplorationLeadPosition('lead', [6.6, 46.6]);
        expect(cones()).not.toEqual(original);
        Layers.updateExplorationLeadPosition('lead', [6.5, 46.5]);
        expect(cones()).toEqual(original);
        sources.clear();
        layers.clear();
        Layers.refreshExplorationLeadsLayer();
        expect(cones()).toEqual(original);
        expect(layers.get('exploration-leads-cones-layer')).toHaveProperty('filter', Layers.getProjectScopedMarkerFilter());
        Layers.removeExplorationLeadMarker('lead');
        expect(cones().features).toEqual([]);
    } finally {
        State.resetLayerState();
        State.map = null;
        Config._projects = null;
    }
});
