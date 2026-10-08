import type { MapCoreMap, MapCoreOptions } from '../../../../../../ts-types/domain/map-core.ts';
import { DEFAULTS } from '../config.ts';
import { State } from '../state.ts';
import { Layers } from './layers.ts';
import { MapSources } from './sources.ts';

export const MapCore = {
    init: function (accessToken: string, containerId = 'map', { fullscreenContainer }: MapCoreOptions = {}) {
        mapboxgl.accessToken = accessToken;
        MapSources.installCheckedTileProtocol();
        MapSources.installCheckedTileFetch();
        const sourceId = MapSources.getCurrentMapSourceId(accessToken);

        const map = new mapboxgl.Map({
            container: containerId,
            style: MapSources.buildInitialMapStyle(sourceId, accessToken),
            center: DEFAULTS.MAP.CENTER,
            zoom: DEFAULTS.MAP.INITIAL_ZOOM,
            projection: 'globe',
            pitchWithRotate: false,
            dragRotate: false,
            touchPitch: false
        });

        map.addControl(new mapboxgl.NavigationControl(), 'top-right');
        map.addControl(new mapboxgl.FullscreenControl(
            fullscreenContainer ? { container: fullscreenContainer } : undefined
        ), 'top-right');
        map.addControl(new mapboxgl.ScaleControl({ maxWidth: DEFAULTS.MAP.SCALE_CONTROL_MAX_WIDTH, unit: 'metric' }), 'bottom-right');
        map.addControl(new mapboxgl.ScaleControl({ maxWidth: DEFAULTS.MAP.SCALE_CONTROL_MAX_WIDTH, unit: 'imperial' }), 'bottom-right');

        // Set state
        State.map = map;
        map.on('remove', () => {
            if (State.map !== map) return;
            Layers.cancelPendingWork();
            State.map = null;
        });

        // Setup Map Height
        this.setupMapHeight(map);

        map.on('load', () => {
            this.hideStreetLevelLabels(map);
            MapSources.applyInitialMapSource(map, sourceId, accessToken);
        });
        map.on('style.load', () => this.hideStreetLevelLabels(map));

        return map;
    },

    hideStreetLevelLabels: function (map: MapCoreMap) {
        // Hide street-level labels while keeping city/place names (matching old implementation)
        const labelsToHide = [
            'road-label', 'road-number-shield', 'road-exit-shield', 'landmark-label',
            'airport-label', 'rail-label', 'water-point-label', 'natural-point-label',
            'transit-label', 'road-crossing', 'road-label-simple', 'road-label-large',
            'road-label-medium', 'road-label-small', 'bridge-case-label', 'bridge-label',
            'tunnel-label', 'ferry-label', 'pedestrian-label', 'aerialway-label',
            'building-label', 'housenum-label'
        ];

        labelsToHide.forEach(layerId => {
            try {
                if (map.getLayer(layerId)) {
                    map.setLayoutProperty(layerId, 'visibility', 'none');
                }
            } catch (e) {
                // Layer might not exist in this style
            }
        });
    },

    setupMapHeight: function (map: MapCoreMap) {
        // Height is handled by CSS (flex-grow/h-full)
        // Just ensure map resizes when window does
        window.addEventListener('resize', () => {
            map.resize();
        });

        // Initial resize to fit container
        setTimeout(() => map.resize(), DEFAULTS.MAP.RESIZE_DELAY_MS);
    },

    setupColorModeToggle: function (map: MapCoreMap) {
        const toggle = document.getElementById('color-mode-toggle') as HTMLInputElement | null;
        const label = document.getElementById('color-mode-label');

        if (!toggle) return;

        toggle.addEventListener('change', function (this: HTMLInputElement) {
            const isDepthMode = this.checked;
            if (label) {
                label.textContent = isDepthMode ? 'Color: By Depth' : 'Color: By Survey';
            }

            // Switch color mode (lines) without changing map style to avoid reloading data
            if (isDepthMode) {
                // map.setStyle('mapbox://styles/mapbox/dark-v11'); // This clears sources
                void Layers.setColorMode('depth');
            } else {
                // map.setStyle('mapbox://styles/mapbox/satellite-streets-v12');
                void Layers.setColorMode('project');
            }

        });
    },

    setupMapSourceControl: function (map: MapCoreMap, accessToken: string) {
        MapSources.renderControl(map, accessToken);
    }
};
