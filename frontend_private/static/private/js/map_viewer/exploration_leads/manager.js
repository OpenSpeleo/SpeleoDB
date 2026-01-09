import { API } from '../api.js';
import { State } from '../state.js';
import { Config } from '../config.js';

// Cache for all exploration leads GeoJSON
let allLeadsGeoJson = null;
let allLeadsFetchPromise = null;

export const ExplorationLeadManager = {
    // Invalidate cache
    invalidateCache() {
        allLeadsGeoJson = null;
        allLeadsFetchPromise = null;
    },

    // Ensure all exploration leads are loaded (single API call)
    async ensureAllLeadsLoaded() {
        if (allLeadsGeoJson && allLeadsGeoJson.type === 'FeatureCollection' && Array.isArray(allLeadsGeoJson.features)) {
            return;
        }

        if (allLeadsFetchPromise) {
            await allLeadsFetchPromise;
            return;
        }

        console.log('🔄 Fetching all exploration leads (GeoJSON) via single API call...');
        allLeadsFetchPromise = API.getAllProjectExplorationLeadsGeoJSON()
            .then(response => {
                if (
                    !response ||
                    response.type !== 'FeatureCollection' ||
                    !Array.isArray(response.features)
                ) {
                    throw new Error('Invalid all-exploration-leads GeoJSON payload');
                }
                allLeadsGeoJson = response;
                console.log(`✅ Cached ${allLeadsGeoJson.features.length} exploration leads from all-leads GeoJSON`);
            })
            .catch(err => {
                console.error('❌ Failed to load all exploration leads GeoJSON:', err);
                allLeadsGeoJson = { type: 'FeatureCollection', features: [] };
            })
            .finally(() => {
                allLeadsFetchPromise = null;
            });

        await allLeadsFetchPromise;
    },

    /**
     * Load exploration leads for a specific project
     * @param {string} projectId - The project UUID
     * @returns {Promise<Array>} Array of exploration lead features
     */
    async loadLeadsForProject(projectId) {
        try {
            // Skip loading leads if user only has WEB_VIEWER access on this project
            const proj = Config.projects.find(p => p.id === String(projectId));
            if (proj && proj.permissions === 'WEB_VIEWER') {
                console.log('⏭️ Skipping exploration leads load for WEB_VIEWER project', projectId);
                return [];
            }

            // Ensure all leads are cached
            await this.ensureAllLeadsLoaded();

            // Filter leads for this project
            const allFc = allLeadsGeoJson || { type: 'FeatureCollection', features: [] };

            const features = allFc.features.filter(f => String(f?.properties?.project) === String(projectId));

            console.log(`✅ Loaded ${features.length} exploration leads for project ${projectId}`);

            // Update State
            features.forEach(feature => {
                const featureId = feature.id;
                if (feature.properties && featureId && feature.geometry) {
                    const coords = feature.geometry.coordinates;
                    State.explorationLeads.set(featureId, {
                        id: featureId,
                        coordinates: coords,
                        description: feature.properties.description || '',
                        projectId: projectId,
                        lineName: 'Survey Line',
                        createdAt: feature.properties.creation_date,
                        createdBy: feature.properties.created_by
                    });
                }
            });

            return features;
        } catch (error) {
            console.error(`Error loading exploration leads for project ${projectId}:`, error);
            return [];
        }
    },

    /**
     * Load all exploration leads for all accessible projects
     * @returns {Promise<Array>} Array of all exploration lead features
     */
    async loadAllLeads() {
        const allFeatures = [];

        // Load leads for each project user has read access to (excludes WEB_VIEWER)
        for (const project of Config.projects) {
            // Skip projects with only web viewer permission
            if (!Config.hasProjectReadAccess(project.id)) {
                continue;
            }

            try {
                const features = await this.loadLeadsForProject(project.id);
                allFeatures.push(...features);
            } catch (error) {
                console.error(`Error loading leads for project ${project.id}:`, error);
            }
        }

        console.log(`✅ Loaded ${allFeatures.length} total exploration leads`);
        return allFeatures;
    },

    /**
     * Create a new exploration lead
     * @param {string} projectId - The project UUID
     * @param {Array} coordinates - [lng, lat] coordinates
     * @param {string} description - Lead description
     * @returns {Promise<Object>} The created lead data
     */
    async createLead(projectId, coordinates, description) {
        const leadData = {
            latitude: coordinates[1].toFixed(7),
            longitude: coordinates[0].toFixed(7),
            description: description
        };

        const response = await API.createExplorationLead(projectId, leadData);

        if (response && response.success && response.data) {
            const lead = response.data;

            // Store in state
            State.explorationLeads.set(lead.id, {
                id: lead.id,
                coordinates: [parseFloat(lead.longitude), parseFloat(lead.latitude)],
                description: lead.description || '',
                projectId: projectId,
                lineName: 'Survey Line',
                createdAt: lead.creation_date,
                createdBy: lead.created_by
            });

            // Invalidate cache so next refresh fetches fresh data
            this.invalidateCache();

            console.log(`✅ Created exploration lead: ${lead.id}`);
            return lead;
        }

        throw new Error('Failed to create exploration lead');
    },

    /**
     * Update an existing exploration lead
     * @param {string} leadId - The lead UUID
     * @param {Object} data - Data to update (description, latitude, longitude)
     * @returns {Promise<Object>} The updated lead data
     */
    async updateLead(leadId, data) {
        const response = await API.updateExplorationLead(leadId, data);

        if (response && response.success && response.data) {
            const lead = response.data;

            // Update in state
            const existing = State.explorationLeads.get(leadId);
            if (existing) {
                State.explorationLeads.set(leadId, {
                    ...existing,
                    coordinates: [parseFloat(lead.longitude), parseFloat(lead.latitude)],
                    description: lead.description || ''
                });
            }

            console.log(`✅ Updated exploration lead: ${leadId}`);
            return lead;
        }

        throw new Error('Failed to update exploration lead');
    },

    /**
     * Delete an exploration lead
     * @param {string} leadId - The lead UUID
     * @returns {Promise<void>}
     */
    async deleteLead(leadId) {
        await API.deleteExplorationLead(leadId);

        // Remove from state
        State.explorationLeads.delete(leadId);

        // Invalidate cache so next refresh fetches fresh data
        this.invalidateCache();

        console.log(`✅ Deleted exploration lead: ${leadId}`);
    },

    /**
     * Move an exploration lead to new coordinates
     * @param {string} leadId - The lead UUID
     * @param {Array} newCoords - [lng, lat] new coordinates
     * @returns {Promise<Object>} The updated lead data
     */
    async moveLead(leadId, newCoords) {
        return this.updateLead(leadId, {
            latitude: newCoords[1].toFixed(7),
            longitude: newCoords[0].toFixed(7)
        });
    }
};
