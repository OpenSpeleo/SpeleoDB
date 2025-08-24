const MapViewer = {

    // Maximally distinguishable color palette based on perceptual color theory
    // These 20 colors are optimized for maximum visual distinction
    colors: [
        '#e41a1c', // Red
        '#377eb8', // Blue  
        '#4daf4a', // Green
        '#984ea3', // Purple
        '#ff7f00', // Orange
        '#ffff33', // Yellow
        '#a65628', // Brown
        '#f781bf', // Pink
        '#999999', // Gray
        '#66c2a5', // Teal
        '#fc8d62', // Salmon
        '#8da0cb', // Lavender
        '#e78ac3', // Rose
        '#a6d854', // Lime
        '#ffd92f', // Gold
        '#e5c494', // Tan
        '#b3b3b3', // Light Gray
        '#1b9e77', // Dark Teal
        '#d95f02', // Dark Orange
        '#7570b3'  // Slate Blue
    ],

    customize_map(map) {
        // Hide street-level labels while keeping city/place names
        const labelsToHide = [
            'road-label',  // Street names
            'road-number-shield',  // Road numbers
            'road-exit-shield',  // Highway exit numbers
            'poi-label',  // Points of interest
            'airport-label',  // Airport labels
            'rail-label',  // Rail/transit labels
            'transit-label',  // Transit stop labels
            'road-crossing',  // Crossing labels
            'road-label-simple',  // Simple road labels
            'road-label-large',  // Large road labels
            'road-label-medium',  // Medium road labels
            'road-label-small',  // Small road labels
            'bridge-case-label',  // Bridge labels
            'bridge-label',  // Bridge labels
            'tunnel-label',  // Tunnel labels
            'ferry-label',  // Ferry labels
            'pedestrian-label',  // Pedestrian path labels
            'aerialway-label',  // Aerial way labels
            'building-label',  // Building labels
            'housenum-label'  // House number labels
        ];

        // Try to hide each label layer - some may not exist in this style
        labelsToHide.forEach(layerId => {
            try {
                if (map.getLayer(layerId)) {
                    map.setLayoutProperty(layerId, 'visibility', 'none');
                }
            } catch (e) {
                // Layer might not exist in this style, which is fine
            }
        }); console.log('Street labels hidden, keeping only place/city names');

        // More comprehensive approach: inspect all layers and hide based on patterns
        const style = map.getStyle();
        if (style && style.layers) {
            style.layers.forEach(layer => {
                if (layer.type === 'symbol' && layer.id) {
                    // Hide layers that contain road/street/poi related terms
                    if (layer.id.includes('road') ||
                        layer.id.includes('street') ||
                        layer.id.includes('highway') ||
                        layer.id.includes('motorway') ||
                        layer.id.includes('trunk') ||
                        layer.id.includes('primary') ||
                        layer.id.includes('secondary') ||
                        layer.id.includes('tertiary') ||
                        layer.id.includes('residential') ||
                        layer.id.includes('service') ||
                        layer.id.includes('link') ||
                        layer.id.includes('pedestrian') ||
                        layer.id.includes('poi') ||
                        layer.id.includes('airport') && !layer.id.includes('airport-label-major') ||
                        layer.id.includes('rail') ||
                        layer.id.includes('transit') ||
                        layer.id.includes('bridge') ||
                        layer.id.includes('tunnel') ||
                        layer.id.includes('ferry') ||
                        layer.id.includes('path') ||
                        layer.id.includes('track') ||
                        layer.id.includes('steps') ||
                        layer.id.includes('building') ||
                        layer.id.includes('housenum') ||
                        layer.id.includes('address')) {

                        // Don't hide if it's a place/city/settlement layer
                        if (!layer.id.includes('place') &&
                            !layer.id.includes('city') &&
                            !layer.id.includes('town') &&
                            !layer.id.includes('village') &&
                            !layer.id.includes('settlement') &&
                            !layer.id.includes('country') &&
                            !layer.id.includes('state')) {

                            try {
                                map.setLayoutProperty(layer.id, 'visibility', 'none');
                            } catch (e) {
                                console.warn(`Could not hide layer ${layer.id}:`, e);
                            }
                        }
                    }
                }
            });
        }

    },

    // Simple function to set map height
    setMapHeight() {
        const mapElement = $('#map');
        const rect = mapElement[0].getBoundingClientRect();

        const newHeight = Math.max(window.innerHeight - rect.top - 20, 600);

        // mapElement.style.height = newHeight + 'px';
        mapElement.height(newHeight);
    },

    // Update legend visibility based on active mode
    updateDepthLegendVisibility() {
        try {
            const legend = $('#depth-scale-fixed');
            if (!legend) {
                // TODO: Add error modal
                return;
            }

            const shouldShow = (window.colorMode === 'depth' && window.depthAvailable === true);
            legend.css('display', shouldShow ? 'block' : 'none');

            // Also hide depth cursor indicator when legend hidden
            if (!shouldShow) {
                const cursor = $('#depth-cursor-indicator');
                const label = $('#depth-cursor-label');
                if (cursor) cursor.hide();
                if (label) label.hide();
            }
        } catch (e) {
            alert(e);
            // TODO: Add error modal
            return;
        }
    },

    // Switch color mode helper
    setColorMode(map, mode) {
        if (mode !== 'depth' && mode !== 'project') return;
        window.colorMode = mode;
        try { localStorage.setItem('map_color_mode', mode); } catch (e) { }
        this._applyColorModeToAllLines(map);
        this.updateDepthLegendVisibility();
        // Update UI state if present
        try {
            const depthBtn = document.getElementById('btn-color-depth');
            const catBtn = document.getElementById('btn-color-project');
            if (depthBtn && catBtn) {
                if (mode === 'depth') {
                    depthBtn.classList.add('active');
                    catBtn.classList.remove('active');
                } else {
                    catBtn.classList.add('active');
                    depthBtn.classList.remove('active');
                }
            }
        } catch (e) { }
    },

    // Initialize color mode toggle UI and state (header toggle)
    initialize_color_mode(map) {
        try {
            const toggle = document.getElementById('color-mode-toggle');
            const label = document.getElementById('color-mode-label');
            const button = document.getElementById('color-mode-button');
            if (toggle && label) {
                // ON means By Survey
                const syncUI = () => {
                    toggle.checked = (window.colorMode === 'project');
                    if (window.colorMode === 'project') {
                        label.textContent = 'Color: By Survey';
                    } else {
                        label.textContent = 'Color: By Depth';
                    }
                };
                toggle.addEventListener('change', () => {
                    this.setColorMode(map, toggle.checked ? 'project' : 'depth');
                    syncUI();
                });
                if (button) {
                    button.addEventListener('click', () => {
                        toggle.checked = !toggle.checked;
                        this.setColorMode(map, toggle.checked ? 'project' : 'depth');
                        syncUI();
                    });
                }
                syncUI();
            }
        } catch (e) { }
    },

    // Compute the paint value for line color based on the active color mode
    // - 'depth': interpolate by feature.properties.depth_norm if available, else fallback to project color
    // - 'project': always use the project's categorical color
    computeLineColorPaint(projectColor) {
        if (window.colorMode === 'project') {
            return projectColor;
        }
        if (window.depthAvailable === true) {
            return [
                'case',
                ['has', 'depth_norm'],
                ['interpolate', ['linear'], ['get', 'depth_norm'],
                    0, '#4575b4',
                    0.5, '#e6f598',
                    1, '#d73027'
                ],
                projectColor
            ];
        }
        return projectColor;
    },

    // -------------- VISIBILITY -------------- //



    // Function to toggle layer visibility for a project
    toggleProjectVisibility(projectId, isVisible) {
        console.log(`Toggling project ${projectId} visibility to: ${isVisible}`);

        // Toggle survey lines/polygons
        if (window.AppState.allProjectLayers.has(projectId)) {
            const layerIds = window.AppState.allProjectLayers.get(projectId);
            const visibility = isVisible ? 'visible' : 'none';

            layerIds.forEach(layerId => {
                try {
                    if (ApplicationState.map.getLayer(layerId)) {
                        ApplicationState.map.setLayoutProperty(layerId, 'visibility', visibility);
                        console.log(`Set ${layerId} visibility to ${visibility}`);
                    }
                } catch (error) {
                    console.warn(`Failed to toggle visibility for layer ${layerId}:`, error);
                }
            });
        }

        // Toggle station markers
        if (stationMarkers.has(projectId)) {
            const markers = stationMarkers.get(projectId);
            const currentZoom = ApplicationState.map.getZoom();
            const shouldShowStations = currentZoom >= 14; // Respect zoom threshold

            markers.forEach(marker => {
                if (isVisible && shouldShowStations) {
                    // Show marker if project is visible AND we're zoomed in enough
                    if (!marker.addedToMap) {
                        marker.addTo(ApplicationState.map);
                        marker.addedToMap = true;
                    }
                } else {
                    // Hide marker if project is hidden OR we're zoomed out
                    if (marker.addedToMap) {
                        marker.remove();
                        marker.addedToMap = false;
                    }
                }
            });

            console.log(`Toggled ${markers.length} station markers for project ${projectId}`);
        }

        // Update state
        projectLayerStates.set(projectId, isVisible);
    },

    // -------------- GOTOS -------------- //

    // Function to fly to a POI on the map
    goToPOI(poiId, latitude, longitude) {
        console.log(`🚁 Flying to POI ${poiId} at ${latitude}, ${longitude}`);

        // Close the POI manager modal
        const poiManagerModal = document.getElementById('poi-manager-modal');
        if (poiManagerModal) {
            poiManagerModal.classList.add('hidden');
        }

        // Fly to the location
        ApplicationState.map.flyTo({
            center: [longitude, latitude],
            zoom: 18, // Max zoom to focus on the POI
            duration: 2000, // 2 second animation
            essential: true, // This animation is essential with respect to prefers-reduced-motion
            pitch: 0,
            bearing: 0
        });

        // Highlight the POI marker
        const marker = poiMarkers.find(m => m.poiId === poiId);
        if (marker) {
            const element = marker.getElement();
            element.classList.add('highlight');
            setTimeout(() => element.classList.remove('highlight'), 3000);
        }
    },

    // Function to fly to a station on the map
    goToStation(stationId, latitude, longitude) {
        console.log(`🚁 Flying to station ${stationId} at ${latitude}, ${longitude}`);

        // Close the station manager modal
        const stationManagerModal = document.getElementById('station-manager-modal');
        if (stationManagerModal) {
            stationManagerModal.classList.add('hidden');
        }

        // Find the station's project ID
        let stationProjectId = null;
        const station = allStations.get(stationId);
        if (station) {
            stationProjectId = station.projectId || station.project || station.project_id;
        }

        // If the project is hidden, toggle it to visible
        if (stationProjectId && projectLayerStates.get(stationProjectId) === false) {
            toggleProjectVisibility(stationProjectId, true);
        }

        // Fly to the location
        ApplicationState.map.flyTo({
            center: [longitude, latitude],
            zoom: 18, // Max zoom to focus on the station
            duration: 2000, // 2 second animation
            essential: true, // This animation is essential with respect to prefers-reduced-motion
            pitch: 0,
            bearing: 0
        });
    },

    // ============================ PRIVATE FUNCTIONS ============================= //

    // Apply color mode to all existing project line layers
    _applyColorModeToAllLines(map) {
        if (!window.projectBoundsMap || !map) return;
        try {
            for (const [projectId, projectData] of window.projectBoundsMap.entries()) {
                const lineLayerId = `project-line-${projectId}`;
                const projectColor = projectData.color;
                const paint = this.computeLineColorPaint(projectColor);
                try {
                    map.setPaintProperty(lineLayerId, 'line-color', paint);
                } catch (e) {
                    // layer might not be present (different geometry), ignore
                }
            }
        } catch (e) {
            // ignore
        }
    },
};