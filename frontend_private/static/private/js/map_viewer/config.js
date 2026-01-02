import { API } from './api.js';

export const Config = {
    // Private storage for projects loaded from API
    _projects: null,

    // Private storage for networks loaded from API
    _networks: null,

    get projects() {
        return this._projects || [];
    },

    get projectIds() {
        return this.projects.map(p => p.id);
    },

    get networks() {
        return this._networks || [];
    },

    get networkIds() {
        return this.networks.map(n => n.id);
    },

    // Load projects from API (call this early in initialization)
    async loadProjects() {
        if (this._projects) {
            return this._projects;
        }

        try {
            console.log('🔄 Loading projects from API...');
            const response = await API.getAllProjects();

            if (response && response.success && Array.isArray(response.data)) {
                // Map API response to expected format (permission -> permissions)
                this._projects = response.data.map(p => ({
                    id: p.id,
                    name: p.name,
                    permissions: p.permission,  // API returns 'permission', code expects 'permissions'
                    description: p.description,
                    country: p.country,
                    latitude: p.latitude,
                    longitude: p.longitude,
                    visibility: p.visibility,
                    geojson_url: p.geojson_url,  // If available
                }));
                console.log(`✅ Loaded ${this._projects.length} projects from API`);
            } else {
                console.error('❌ Invalid projects response:', response);
                this._projects = [];
            }
        } catch (error) {
            console.error('❌ Failed to load projects from API:', error);
            this._projects = [];
        }

        return this._projects;
    },

    // Load networks from API (call this early in initialization)
    async loadNetworks() {
        if (this._networks) {
            return this._networks;
        }

        try {
            console.log('🔄 Loading surface networks from API...');
            const response = await API.getAllSurfaceNetworks();

            if (response && response.success && Array.isArray(response.data)) {
                // Map API response to expected format
                this._networks = response.data.map(n => ({
                    id: n.id,
                    name: n.name,
                    description: n.description,
                    is_active: n.is_active,
                    created_by: n.created_by,
                    creation_date: n.creation_date,
                    modified_date: n.modified_date,
                    permissions: n.user_permission_level_label,  // API returns permission label
                    permission_level: n.user_permission_level,   // Numeric level
                }));
                console.log(`✅ Loaded ${this._networks.length} surface networks from API`);
            } else {
                console.error('❌ Invalid networks response:', response);
                this._networks = [];
            }
        } catch (error) {
            console.error('❌ Failed to load networks from API:', error);
            this._networks = [];
        }

        return this._networks;
    },

    // Helper: does the user have read access on a specific project? (excludes WEB_VIEWER)
    hasProjectReadAccess: function (projectId) {
        try {
            const proj = this.projects.find(p => p.id === String(projectId));
            if (!proj) return false;
            // READ_ONLY, READ_AND_WRITE, and ADMIN have read access (not WEB_VIEWER)
            return proj.permissions === 'READ_ONLY' || 
                   proj.permissions === 'READ_AND_WRITE' || 
                   proj.permissions === 'ADMIN';
        } catch (e) {
            return false;
        }
    },

    // Helper: does the user have write access on a specific project?
    hasProjectWriteAccess: function (projectId) {
        try {
            const proj = this.projects.find(p => p.id === String(projectId));
            if (!proj) return false;
            // Treat READ_AND_WRITE and ADMIN as write access
            return proj.permissions === 'READ_AND_WRITE' || proj.permissions === 'ADMIN';
        } catch (e) {
            return false;
        }
    },

    // Helper: does the user have admin access on a specific project?
    hasProjectAdminAccess: function (projectId) {
        try {
            const proj = this.projects.find(p => p.id === String(projectId));
            if (!proj) return false;
            return proj.permissions === 'ADMIN';
        } catch (e) {
            return false;
        }
    },

    // Helper: does the user have write access on a specific network?
    hasNetworkWriteAccess: function (networkId) {
        try {
            if (!networkId) {
                console.warn('⚠️ hasNetworkWriteAccess called with no networkId');
                return false;
            }
            const network = this.networks.find(n => n.id === String(networkId));
            if (!network) {
                console.warn(`⚠️ Network ${networkId} not found in Config.networks. Available:`, this.networks.map(n => n.id));
                return false;
            }
            // Treat READ_AND_WRITE and ADMIN as write access
            // permission_level: 1=READ_ONLY, 2=READ_AND_WRITE, 3=ADMIN
            const hasAccess = network.permission_level >= 2;
            console.log(`🔐 hasNetworkWriteAccess(${networkId}): permission_level=${network.permission_level}, hasAccess=${hasAccess}`);
            return hasAccess;
        } catch (e) {
            console.error('❌ hasNetworkWriteAccess error:', e);
            return false;
        }
    },

    // Helper: does the user have admin access on a specific network?
    hasNetworkAdminAccess: function (networkId) {
        try {
            if (!networkId) {
                console.warn('⚠️ hasNetworkAdminAccess called with no networkId');
                return false;
            }
            const network = this.networks.find(n => n.id === String(networkId));
            if (!network) {
                console.warn(`⚠️ Network ${networkId} not found for admin check`);
                return false;
            }
            // permission_level: 3=ADMIN
            return network.permission_level >= 3;
        } catch (e) {
            console.error('❌ hasNetworkAdminAccess error:', e);
            return false;
        }
    },

    /**
     * Filter projects to only include those with available GeoJSON data.
     * Call this after fetching GeoJSON metadata to remove projects without map data.
     * @param {Array} geojsonMetadata - Array of project metadata with geojson_file field
     */
    filterProjectsByGeoJSON: function (geojsonMetadata) {
        if (!this._projects || !Array.isArray(geojsonMetadata)) {
            return;
        }

        const projectsWithGeoJSON = new Set();

        // Build a set of project IDs that have valid GeoJSON
        geojsonMetadata.forEach(meta => {
            if (meta.geojson_file) {
                projectsWithGeoJSON.add(String(meta.id));
            }
        });

        // Also check for projects that have geojson_url directly set
        this._projects.forEach(p => {
            if (p.geojson_url) {
                projectsWithGeoJSON.add(String(p.id));
            }
        });

        const originalCount = this._projects.length;

        // Filter to only keep projects with GeoJSON
        this._projects = this._projects.filter(p => projectsWithGeoJSON.has(String(p.id)));

        const filteredCount = originalCount - this._projects.length;
        if (filteredCount > 0) {
            console.log(`🗺️ Filtered out ${filteredCount} projects without GeoJSON data`);
        }
        console.log(`✅ ${this._projects.length} projects with GeoJSON available for map viewer`);
    },
    VISIBILITY_PREFS_STORAGE_KEY: 'speleo_project_visibility',
    NETWORK_VISIBILITY_PREFS_STORAGE_KEY: 'speleo_network_visibility'
};
