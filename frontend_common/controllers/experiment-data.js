import { afterWindowLoad } from '../readiness.js';

export async function init(context) {
    await afterWindowLoad();
    'use strict';
        
        // ============================================
        // Global Variables
        // ============================================
        let gridApi = null;
        const experimentId = context.experimentId;
            let experimentFields = null; // Will store field definitions with order and names
        
        // ============================================
        // Data Loading
        // ============================================
        async function loadExperimentData() {
            try {
                showLoading();
                
                // First, fetch experiment details to get field definitions
                const experimentResponse = await fetch(
                    Urls["api:v2:experiment-detail"](experimentId), 
                    { credentials: 'same-origin' }
                );
                
                if (!experimentResponse.ok) {
                    throw new Error(`Failed to fetch experiment details: ${experimentResponse.status}`);
                }
                
                const experimentData = await experimentResponse.json();
                experimentFields = experimentData.data?.experiment_fields || experimentData.experiment_fields || [];
                
                // Sort fields by order parameter
                if (Array.isArray(experimentFields)) {
                    experimentFields.sort((a, b) => {
                        const orderA = a.order !== undefined ? a.order : 999;
                        const orderB = b.order !== undefined ? b.order : 999;
                        return orderA - orderB;
                    });
                }
                
                // Fetch GeoJSON data from the API
                const apiUrl = context.dataUrl;
                const response = await fetch(apiUrl);
                
                if (!response.ok) {
                    throw new Error(`Failed to fetch data: ${response.status} ${response.statusText}`);
                }
                
                const geojsonData = await response.json();
                
                if (!geojsonData || !geojsonData.features || !Array.isArray(geojsonData.features)) {
                    throw new Error('Invalid GeoJSON data format');
                }
                
                // Transform GeoJSON features to table rows
                const rows = transformGeoJSONToRows(geojsonData.features);
                
                // Create grid
                createDataGrid(rows);
                
                // Update stats
                $('#recordCount').text(rows.length);
                $('#columnCount').text(Object.keys(rows[0] || {}).length);
                
                showDataGrid();
                
            } catch (error) {
                console.error('Error loading data:', error);
                showError(error.message);
            }
        }
        
        function transformGeoJSONToRows(features) {
            const rows = [];
            
            features.forEach(feature => {
                const props = feature.properties || {};
                const geometry = feature.geometry || {};
                const coordinates = geometry.coordinates || [];
                
                // Build row object with standard fields first
                const row = {
                    'Project Name': props.project_name || '',
                    'Project ID': props.project_id || '',
                    'Station ID': props.station_id || '',
                    'Station Name': props.station_name || '',
                    'Longitude': coordinates[0] || '',
                    'Latitude': coordinates[1] || '',
                };
                
                // Add experiment fields in the order defined by experiment_fields
                if (experimentFields && Array.isArray(experimentFields)) {
                    experimentFields.forEach(field => {
                        const fieldId = field.id;
                        const fieldName = field.name;
                        
                        // Skip status fields
                        if (fieldName && (fieldName.toLowerCase() === 'status')) {
                            return;
                        }
                        
                        // Get value by field UUID from properties
                        if (fieldId in props) {
                            row[fieldName] = formatValue(props[fieldId]);
                        }
                    });
                } else {
                    // Fallback: if experimentFields not loaded, add all remaining properties
                    const skipFields = ['id', 'station_name', 'station_id', 'project_name', 'project_id', 'created_by', 'status'];
                    
                    Object.keys(props).forEach(key => {
                        if (!skipFields.includes(key) && key.toLowerCase() !== 'status') {
                            // Format field name: flow -> Flow
                            const fieldName = key
                                .replace(/_/g, ' ')
                                .replace(/\b\w/g, l => l.toUpperCase());
                            row[fieldName] = formatValue(props[key]);
                        }
                    });
                }
                
                rows.push(row);
            });
            
            // Remove status columns from all rows to ensure they don't appear anywhere
            const cleanedRows = rows.map(row => {
                const cleanedRow = {};
                Object.keys(row).forEach(key => {
                    if (key.toLowerCase() !== 'status') {
                        cleanedRow[key] = row[key];
                    }
                });
                return cleanedRow;
            });
            
            return cleanedRows;
        }
        
        function formatValue(value) {
            if (value === null || value === undefined) {
                return '';
            }
            if (typeof value === 'object') {
                return JSON.stringify(value);
            }
            return String(value);
        }
        
        // ============================================
        // AG Grid Setup
        // ============================================
        // Custom header name mapping - map field keys to display names
        const headerNameMap = {
            // Add your custom header name mappings here
            // Example: 'Project Name': 'Project',
            // 'Station ID': 'Station Identifier',
        };
        
        // Columns to exclude from the table
        const excludedColumns = ['Status', 'status'];
        
        function createDataGrid(rows) {
            if (rows.length === 0) {
                showError('No data available to display');
                return;
            }
            
            // Generate column definitions from first row
            const firstRow = rows[0];
            const columnDefs = Object.keys(firstRow)
                .filter(key => !excludedColumns.includes(key)) // Filter out excluded columns
                .map(key => ({
                    field: key,
                    headerName: headerNameMap[key] || key, // Use custom name if mapped, otherwise use original
                    sortable: true,
                    filter: true,
                    resizable: true,
                    minWidth: 150,
                    flex: 1,
                }));
            
            // Grid options
            const gridOptions = {
                columnDefs: columnDefs,
                rowData: rows,
                defaultColDef: {
                    sortable: true,
                    filter: true,
                    resizable: true,
                },
                enableCellTextSelection: true,
                ensureDomOrder: true,
                pagination: true,
                paginationPageSize: 50,
                paginationPageSizeSelector: [20, 50, 100, 200],
                animateRows: true,
                rowSelection: 'multiple',
            };
            
            // Create the grid
            const gridDiv = document.querySelector('#dataGrid');
            gridApi = window.agGrid.createGrid(gridDiv, gridOptions);
        }
        
        // ============================================
        // Export to Excel
        // ============================================
        $('#exportExcelBtn').on('click', async function() {
            const $btn = $(this);
            const originalHtml = $btn.html();
            
            try {
                // Disable button and show loading
                $btn.prop('disabled', true).html(`
                    <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Exporting...</span>
                `);
                
                // Call export API
                const response = await fetch(
                    Urls['api:v2:experiment-export-excel'](experimentId), 
                    {
                        method: 'GET',
                        headers: {
                            'X-CSRFToken': context.csrfToken,
                        },
                        credentials: 'same-origin',
                    }
                );
                
                if (!response.ok) {
                    throw new Error(`Export failed: ${response.status} ${response.statusText}`);
                }
                
                // Get filename from Content-Disposition header
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = 'experiment_data.xlsx';
                if (contentDisposition) {
                    // Match filename with or without quotes, but don't include quotes in capture
                    const filenameMatch = contentDisposition.match(/filename=["']?([^"';]+)["']?/);
                    if (filenameMatch && filenameMatch[1]) {
                        filename = filenameMatch[1].trim();
                    }
                }
                
                // Download file with proper MIME type
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
                
                // Show success message
                $btn.removeClass('bg-indigo-600 hover:bg-indigo-700')
                    .addClass('bg-green-600 hover:bg-green-700')
                    .html(`
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                        </svg>
                        <span>Exported!</span>
                    `);
                
                setTimeout(() => {
                    $btn.removeClass('bg-green-600 hover:bg-green-700')
                        .addClass('bg-indigo-600 hover:bg-indigo-700')
                        .html(originalHtml)
                        .prop('disabled', false);
                }, 2000);
                
            } catch (error) {
                console.error('Export error:', error);
                alert('Failed to export data: ' + error.message);
                $btn.html(originalHtml).prop('disabled', false);
            }
        });
        
        // ============================================
        // Refresh Data
        // ============================================
        $('#refreshDataBtn').on('click', function() {
            if (gridApi) {
                gridApi.destroy();
                gridApi = null;
            }
            loadExperimentData();
        });
        
        // ============================================
        // UI State Management
        // ============================================
        function showLoading() {
            $('#loadingSpinner').removeClass('hidden');
            $('#dataGridContainer').addClass('hidden');
            $('#errorMessage').addClass('hidden');
        }
        
        function showDataGrid() {
            $('#loadingSpinner').addClass('hidden');
            $('#dataGridContainer').removeClass('hidden');
            $('#errorMessage').addClass('hidden');
        }
        
        function showError(message) {
            $('#loadingSpinner').addClass('hidden');
            $('#dataGridContainer').addClass('hidden');
            $('#errorMessage').removeClass('hidden');
            $('#errorText').text(message);
        }
        
        // ============================================
        // Initialize
        // ============================================
        loadExperimentData();
}
