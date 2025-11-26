import { Config } from '../config.js';
import { State } from '../state.js';
import { Layers } from './layers.js';

export const MapCore = {
    init: function (accessToken, containerId = 'map') {
        mapboxgl.accessToken = accessToken;

        const map = new mapboxgl.Map({
            container: containerId,
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
            center: [0, 0],
            zoom: 0,
            projection: 'globe', // Enable globe projection for better wide-angle view
            pitchWithRotate: false, // Disable pitch with rotate
            dragRotate: false, // Disable rotation
            touchPitch: false // Disable pitch gestures
        });

        // Add controls
        map.addControl(new mapboxgl.NavigationControl(), 'top-right');
        map.addControl(new mapboxgl.FullscreenControl(), 'top-right');
        map.addControl(new mapboxgl.ScaleControl({ maxWidth: 200, unit: 'metric' }), 'bottom-right');
        map.addControl(new mapboxgl.ScaleControl({ maxWidth: 200, unit: 'imperial' }), 'bottom-right');

        // Set state
        State.map = map;

        // Setup Map Height
        this.setupMapHeight(map);

        map.on('load', () => {
            // Hide street-level labels while keeping city/place names (matching old implementation)
            const labelsToHide = [
                'road-label', 'road-number-shield', 'road-exit-shield', 'poi-label', 
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
        });

        return map;
    },

    setupMapHeight: function(map) {
        // Height is handled by CSS (flex-grow/h-full)
        // Just ensure map resizes when window does
        window.addEventListener('resize', () => {
            map.resize();
        });
        
        // Initial resize to fit container
        setTimeout(() => map.resize(), 100);
    },

    setupColorModeToggle: function(map) {
        const toggle = document.getElementById('color-mode-toggle');
        const label = document.getElementById('color-mode-label');
        
        if (!toggle) return;

        toggle.addEventListener('change', function() {
            const isDepthMode = this.checked;
            if (label) {
                label.textContent = isDepthMode ? 'Color: By Depth' : 'Color: By Survey';
            }
            
            // Switch color mode (lines) without changing map style to avoid reloading data
            if (isDepthMode) {
                // map.setStyle('mapbox://styles/mapbox/dark-v11'); // This clears sources
                Layers.setColorMode('depth');
            } else {
                // map.setStyle('mapbox://styles/mapbox/satellite-streets-v12');
                Layers.setColorMode('project');
            }
            
            // Dispatch event for other listeners
            window.dispatchEvent(new CustomEvent('speleo:color-mode-changed', { detail: { mode: isDepthMode ? 'depth' : 'project' } }));
        });
    }
};


