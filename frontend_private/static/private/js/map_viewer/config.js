import { API } from './api.js';

export const Config = {
    // Private storage for projects loaded from API
    _projects: null,
    
    get projects() {
        return this._projects || [];
    },

    get projectIds() {
        return this.projects.map(p => p.id);
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

    // Helper: does the user have write access on a specific project?
    hasProjectWriteAccess: function(projectId) {
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
    hasProjectAdminAccess: function(projectId) {
        try {
            const proj = this.projects.find(p => p.id === String(projectId));
            if (!proj) return false;
            return proj.permissions === 'ADMIN';
        } catch (e) {
            return false;
        }
    },

    /**
     * Filter projects to only include those with available GeoJSON data.
     * Call this after fetching GeoJSON metadata to remove projects without map data.
     * @param {Array} geojsonMetadata - Array of project metadata with geojson_file field
     */
    filterProjectsByGeoJSON: function(geojsonMetadata) {
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

    VISIBILITY_PREFS_STORAGE_KEY: 'speleo_project_visibility'
};
