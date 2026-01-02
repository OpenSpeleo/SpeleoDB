import { API } from '../api.js';
import { State } from '../state.js';
import { Config } from '../config.js';

export const ExplorationLeadManager = {
    /**
     * Load exploration leads for a specific project
     * @param {string} projectId - The project UUID
     * @returns {Promise<Array>} Array of exploration lead features
     */
    async loadLeadsForProject(projectId) {
        try {
            const response = await API.getProjectExplorationLeads(projectId);
            if (response && response.success && Array.isArray(response.data)) {
                // Store each lead in state and convert to GeoJSON features
                const features = response.data.map(lead => {
                    // Store in state for easy access
                    State.explorationLeads.set(lead.id, {
                        id: lead.id,
                        coordinates: [parseFloat(lead.longitude), parseFloat(lead.latitude)],
                        description: lead.description || '',
                        projectId: projectId,
                        lineName: 'Survey Line', // Will be set from context if available
                        createdAt: lead.creation_date,
                        createdBy: lead.created_by
                    });

                    // Return GeoJSON feature
                    return {
                        type: 'Feature',
                        geometry: {
                            type: 'Point',
                            coordinates: [parseFloat(lead.longitude), parseFloat(lead.latitude)]
                        },
                        properties: {
                            id: lead.id,
                            description: lead.description || '',
                            projectId: projectId
                        }
                    };
                });

                console.log(`✅ Loaded ${features.length} exploration leads for project ${projectId}`);
                return features;
            }
            return [];
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

