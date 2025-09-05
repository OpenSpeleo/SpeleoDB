const Station = {
    // ================== SETUP HANDLER ==================== //

    // Function to setup station modal event handlers
    setupStationModalHandlers() {
        const stationModal = document.getElementById('station-modal');
        const stationModalClose = document.getElementById('station-modal-close');

        if (stationModalClose) {
            // Remove any existing listeners first
            const newClose = stationModalClose.cloneNode(true);
            stationModalClose.parentNode.replaceChild(newClose, stationModalClose);

            // Add fresh listener
            newClose.addEventListener('click', closeStationModal);
        }

        if (stationModal) {
            // Ensure a single, stable backdrop handler exists on window to avoid scope issues
            if (typeof window.modalBackdropHandler !== 'function') {
                window.modalBackdropHandler = function (e) {
                    const modal = document.getElementById('station-modal');
                    if (!modal) return;
                    const dialog = modal.querySelector('.bg-slate-800');
                    // Close if click outside the dialog content
                    if (e.target === modal && dialog && !dialog.contains(e.target)) {
                        closeStationModal();
                    }
                };
            }
            stationModal.removeEventListener('click', window.modalBackdropHandler);
            stationModal.addEventListener('click', window.modalBackdropHandler);
        }
    },
    // ================== LOADING OVERLAY ================== //

    showLoadingOverlay(title, message) {
        const overlay = document.createElement('div');
        overlay.className = 'custom-loading-overlay';
        overlay.innerHTML = `
            <div class="loading-card">
                <div class="loading-spinner"></div>
                <div class="loading-title">${title}</div>
                <div class="loading-message">${message}</div>
            </div>
        `;

        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            animation: fadeIn 0.2s ease-out;
        `;

        const card = overlay.querySelector('.loading-card');
        card.style.cssText = `
            background: rgba(51, 65, 85, 0.98);
            padding: 32px;
            border-radius: 16px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(148, 163, 184, 0.3);
            min-width: 280px;
        `;

        const spinner = overlay.querySelector('.loading-spinner');
        spinner.style.cssText = `
            width: 48px;
            height: 48px;
            border: 3px solid rgba(56, 189, 248, 0.2);
            border-left: 3px solid #38bdf8;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        `;

        const titleEl = overlay.querySelector('.loading-title');
        titleEl.style.cssText = `
            color: #f1f5f9;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 8px;
        `;

        const messageEl = overlay.querySelector('.loading-message');
        messageEl.style.cssText = `
            color: #94a3b8;
            font-size: 14px;
        `;

        document.body.appendChild(overlay);

        return overlay;
    },

    hideLoadingOverlay(overlay) {
        if (overlay) {
            overlay.style.animation = 'fadeOut 0.2s ease-out';
            setTimeout(() => overlay.remove(), 200);
        }
    },

    // ======================= EDITION ======================== //

    cancelEdit(stationId) {
        console.log(`❌ Checking for unsaved changes before cancelling edit for station ${stationId}`);

        // Store the station ID for later use
        window.pendingCancelStationId = stationId;

        // Check if there are unsaved changes
        const form = document.getElementById('edit-station-form');
        if (form && window.originalStationValues) {
            const currentValues = {
                name: form.querySelector('input[name="name"]').value,
                description: form.querySelector('textarea[name="description"]').value,
                latitude: parseFloat(form.querySelector('input[name="latitude"]').value),
                longitude: parseFloat(form.querySelector('input[name="longitude"]').value),
                project_id: form.querySelector('select[name="project_id"]').value
            };

            // Check if any values changed
            let hasChanges = false;
            for (const key in currentValues) {
                if (currentValues[key] !== window.originalStationValues[key]) {
                    hasChanges = true;
                    break;
                }
            }

            // If there are changes, show confirmation modal
            if (hasChanges) {
                // Show the cancel confirmation modal
                $('#cancel-edit-modal').css("display", "flex");
                return;
            }
        }

        // No changes, proceed with cancel
        proceedWithCancelEdit(stationId);
    },

    closeCancelEditModal() {
        $('#cancel-edit-modal').hide();
        window.pendingCancelStationId = null;
    },

    // ===================== DELETE ================== //

    delete(stationId, projectId) {
        console.log(`🗑️ Preparing to delete station ${stationId} in project ${projectId}`);
        if (!projectId || !Utils.hasProjectWriteAccess(projectId)) {
            showNotification('warning', 'You have read access and cannot modify.');
            return;
        }

        const station = allStations.get(stationId);
        const stationName = station?.name || 'Station';

        // Store data for modal
        window.pendingDeleteStation = {
            stationId,
            projectId,
            stationName,
            station
        };

        // Show beautiful confirmation modal
        _showDeleteConfirmModal(station, stationId);
    },

    confirmDelete() {
        if (!window.pendingDeleteStation) return;

        const { stationId, projectId, stationName } = window.pendingDeleteStation;
        if (!projectId || !Utils.hasProjectAdminAccess(projectId)) {
            showNotification('warning', 'Only admins can delete stations.');
            return;
        }

        console.log(`🗑️ Starting delete for station ${stationId} in project ${projectId}`);
        console.log(`🗑️ Station found: ${stationName}`);

        // Hide the modal
        document.getElementById('delete-confirm-modal').style.display = 'none';

        // Show loading overlay
        const loadingOverlay = Station.showLoadingOverlay(
            'Deleting Station',
            `Removing "${stationName}" and all its resources...`
        );

        try {
            // Call delete API
            deleteStationAPI(stationId);

            console.log(`✅ API delete successful for ${stationId}`);



            // Remove from global stations map
            if (allStations.has(stationId)) {
                allStations.delete(stationId);
                console.log(`🗑️ Removed from allStations map`);
            }

            // Find and remove the marker from the map
            console.log(`🔍 Looking for markers in project ${projectId}`);
            if (stationMarkers.has(projectId)) {
                const markers = stationMarkers.get(projectId);
                console.log(`🔍 Found ${markers.length} markers in project`);

                // Debug: log all marker IDs
                markers.forEach((m, i) => {
                    console.log(`  Marker ${i}: stationId=${m.stationId}, name=${m.stationName}`);
                });

                const markerIndex = markers.findIndex(m => m.stationId === stationId);
                console.log(`🔍 Marker index: ${markerIndex}`);

                if (markerIndex !== -1) {
                    const marker = markers[markerIndex];
                    console.log(`🗑️ Found marker to remove, addedToMap: ${marker.addedToMap}`);

                    // Always try to remove the marker
                    try {
                        marker.remove();
                        console.log(`🗑️ Marker removed from map`);
                    } catch (e) {
                        console.error(`❌ Error removing marker:`, e);
                    }

                    markers.splice(markerIndex, 1);
                    console.log(`🗑️ Removed marker from array, remaining: ${markers.length}`);
                } else {
                    console.warn(`⚠️ Could not find marker with stationId ${stationId}`);
                    // Try alternative search by name
                    const markerByName = markers.findIndex(m => m.stationName === stationName);
                    if (markerByName !== -1) {
                        console.log(`🔍 Found marker by name instead`);
                        try {
                            markers[markerByName].remove();
                        } catch (e) {
                            console.error(`❌ Error removing marker by name:`, e);
                        }
                        markers.splice(markerByName, 1);
                    }
                }
            } else {
                console.warn(`⚠️ No markers found for project ${projectId}`);
            }

            // Close the modal
            closeStationModal();

            // Show success notification
            showNotification('success', `Station "${stationName}" deleted successfully`);
            console.log(`✅ Deleted station: ${stationName} (${stationId})`);

            // Force update visibility in case we're zoomed in
            if (window.updateStationVisibility) {
                window.updateStationVisibility();
            }

            // Reload stations to ensure consistency
            console.log(`🔄 Scheduling reload of stations for project ${projectId}`);
            setTimeout(() => {
                console.log(`🔄 Reloading stations now...`);
                loadStationsForProject(projectId).then(() => {
                    console.log(`✅ Station reload complete after delete`);
                    // Update visibility again after reload
                    if (window.updateStationVisibility) {
                        window.updateStationVisibility();
                    }
                });
            }, 500);

        } catch (error) {
            console.error('Error deleting station:', error);
            showNotification('error', `Failed to delete station: ${error.message}`);
        } finally {
            Station.hideLoadingOverlay(loadingOverlay);
            window.pendingDeleteStation = null;
        }
    },

    cancelDelete() {
        $('#delete-confirm-modal').hide();
        window.pendingDeleteStation = null;
    }
};





function _showDeleteConfirmModal(station, stationId) {
    const modal = document.getElementById('delete-confirm-modal');
    const messageEl = document.getElementById('delete-confirm-message');
    const detailsEl = document.getElementById('delete-confirm-details');

    const stationName = station?.name || 'Station';
    const resourceCount = station?.resource_count || 0;
    const createdBy = station?.created_by_email || station?.created_by || 'Unknown';
    const creationDate = station?.creation_date ? new Date(station.creation_date).toLocaleDateString() : 'Unknown';

    // Update message
    messageEl.innerHTML = `Are you sure you want to permanently delete <strong>"${stationName}"</strong>?`;

    // Update details
    detailsEl.innerHTML = `
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Station Name:</span>
                <span class="drag-confirm-value">${stationName}</span>
            </div>
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Location:</span>
                <span class="drag-confirm-value">
                    ${station?.latitude ? station.latitude.toFixed(7) : 'Unknown'}, ${station?.longitude ? station.longitude.toFixed(7) : 'Unknown'}
                </span>
            </div>
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Resources:</span>
                <span class="drag-confirm-value" style="${resourceCount > 0 ? 'color: #f87171; font-weight: 600;' : ''}">
                    ${resourceCount} ${resourceCount === 1 ? 'resource' : 'resources'}
                </span>
            </div>
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Created By:</span>
                <span class="drag-confirm-value">${createdBy}</span>
            </div>
            <div class="drag-confirm-detail-row">
                <span class="drag-confirm-label">Created On:</span>
                <span class="drag-confirm-value">${creationDate}</span>
            </div>
        `;

    // Show modal
    modal.style.display = 'flex';
}


