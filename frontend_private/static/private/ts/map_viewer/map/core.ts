import { attachGlobeAtmosphere } from '@speleodb/map-viewer';
import { Renderer } from './renderer.ts';
import { normalizeMapboxRequest, normalizeProviderStyle, createMapboxAttributionControl, withoutMapboxFeedback } from './mapbox_provider.ts';
import type { MapCoreMap, MapCoreOptions } from '../../../../../../ts-types/domain/map-core.ts';
import { DEFAULTS } from '../config.ts';
import { State } from '../state.ts';
import { Layers } from './layers.ts';
import { MapSources } from './sources.ts';

export const MapCore = {
    init: function (accessToken: string, containerId = 'map', { fullscreenContainer }: MapCoreOptions = {}): MapCoreMap {
        MapSources.installCheckedTileProtocol();
        const sourceId = MapSources.getCurrentMapSourceId(accessToken);

        const map = new Renderer.Map({
            container: containerId,
            style: null,
            center: DEFAULTS.MAP.CENTER,
            zoom: DEFAULTS.MAP.INITIAL_ZOOM,
            transformRequest: url => normalizeMapboxRequest(url, accessToken),
            attributionControl: false,
            pitchWithRotate: false,
            dragRotate: false,
            touchPitch: false
        });
        attachGlobeAtmosphere(map);
        map.addControl(withoutMapboxFeedback(new Renderer.AttributionControl()), 'bottom-right');

        // Observability hook exposes this instance without installing a renderer global.
        window.dispatchEvent(new CustomEvent('speleo:map-created', { detail: { map } }));

        // A token means the retained Mapbox base style also supplies overlay glyphs.
        if (accessToken) map.addControl(createMapboxAttributionControl(), 'bottom-left');
        map.addControl(new Renderer.NavigationControl(), 'top-right');
        map.addControl(new Renderer.FullscreenControl(
            fullscreenContainer ? { container: fullscreenContainer } : undefined
        ), 'top-right');
        map.addControl(new Renderer.ScaleControl({ maxWidth: DEFAULTS.MAP.SCALE_CONTROL_MAX_WIDTH, unit: 'metric' }), 'bottom-right');
        map.addControl(new Renderer.ScaleControl({ maxWidth: DEFAULTS.MAP.SCALE_CONTROL_MAX_WIDTH, unit: 'imperial' }), 'bottom-right');

        // Set state
        State.map = map;
        map.on('remove', () => {
            removeMapHeightHandlers();
            if (State.map !== map) return;
            Layers.cancelPendingWork();
            State.map = null;
        });

        // Setup Map Height
        const removeMapHeightHandlers = this.setupMapHeight(map);

        map.on('load', () => {
            this.hideStreetLevelLabels(map);
            MapSources.applyInitialMapSource(map, sourceId, accessToken);
        });
        let initialStyleLoaded = false;
        map.on('style.load', () => {
            if (!initialStyleLoaded) {
                initialStyleLoaded = true;
                // The style installs the globe projection. Before this point,
                // Mercator viewport constraints can raise the constructor zoom.
                // Restore the startup camera once, before load-time data fitting.
                map.jumpTo({ center: DEFAULTS.MAP.CENTER, zoom: DEFAULTS.MAP.INITIAL_ZOOM });
            }
            this.hideStreetLevelLabels(map);
        });
        // Start native asynchronous loading after registering both style handlers.
        // The transform corrects the provider projection before style validation.
        map.setStyle(MapSources.buildInitialMapStyle(sourceId, accessToken), {
            transformStyle: normalizeProviderStyle,
        });

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
        const resize = () => { map.resize(); };
        window.addEventListener('resize', resize);

        // Initial resize to fit container
        const timeout = setTimeout(resize, DEFAULTS.MAP.RESIZE_DELAY_MS);
        return () => {
            window.removeEventListener('resize', resize);
            clearTimeout(timeout);
        };
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
