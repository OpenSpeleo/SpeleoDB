// POI Modal Functions
window.openPOIModal = function (poiId = null, isNewlyCreated = false) {
    console.log(`📋 Opening POI modal for: ${poiId || 'NEW POI'}`);

    const poi = poiId ? allPOIs.get(poiId) : null;
    if (!poi && poiId) {
        console.error(`❌ POI ${poiId} not found`);
        showNotification('error', 'Point of Interest not found');
        return;
    }

    const hasWriteAccess = window.hasWriteAccess || false;

    // Create modal HTML
    const modalHTML = `
        <div id="poi-details-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-2xl">
                <div class="flex items-center justify-between p-6 border-b border-slate-600">
                    <h2 class="text-xl font-semibold text-white">
                        ${poi ? `Point of Interest: ${poi.name}` : 'Point of Interest Details'}
                        ${isNewlyCreated ? '<span class="ml-2 text-sm text-emerald-400">✨ Newly Created</span>' : ''}
                    </h2>
                    <button onclick="closePOIModal()" class="text-slate-400 hover:text-white transition-colors">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                
                <div class="p-6">
                    ${poi ? `
                        <div class="space-y-4">
                            <div>
                                <h3 class="text-lg font-semibold text-white mb-2">${poi.name}</h3>
                                ${poi.description ? `<p class="text-slate-300">${poi.description}</p>` : '<p class="text-slate-400 italic">No description</p>'}
                            </div>
                            
                            <div class="bg-slate-700/50 rounded-lg p-4 space-y-2">
                                <p class="text-slate-300">
                                    <strong>Coordinates:</strong> ${Number(poi.latitude).toFixed(7)}, ${Number(poi.longitude).toFixed(7)}
                                </p>
                                <p class="text-slate-300">
                                    <strong>Created by:</strong> ${poi.created_by_email || 'Unknown'}
                                </p>
                                <p class="text-slate-300">
                                    <strong>Created:</strong> ${poi.creation_date ? new Date(poi.creation_date).toLocaleDateString() : 'Unknown'}
                                </p>
                            </div>
                            
                            ${hasWriteAccess ? `
                                <div class="flex justify-end space-x-3 pt-4 border-t border-slate-600 mt-4">
                                    <button onclick="editPOI('${poi.id}')" class="btn-secondary" style="min-width: 120px;">
                                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                                        </svg>
                                        Edit
                                    </button>
                                    <button onclick="showDeletePOIConfirmModal({ id: '${poi.id}', name: '${poi.name}' })" class="btn-danger" style="min-width: 120px;">
                                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                        </svg>
                                        Delete
                                    </button>
                                </div>
                            ` : ''}
                        </div>
                    ` : `
                        <div class="text-center py-8">
                            <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                            </svg>
                            <h3 class="text-white text-lg font-medium mb-2">Point of Interest Not Found</h3>
                            <p class="text-slate-400">This Point of Interest could not be loaded.</p>
                        </div>
                    `}
                </div>
            </div>
        </div>
    `;

    // Add modal to body
    const existingModal = document.getElementById('poi-details-modal');
    if (existingModal) {
        existingModal.remove();
    }
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Add escape key handler
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            closePOIModal();
        }
    };
    document.addEventListener('keydown', escHandler);
    window._poiModalEscHandler = escHandler;
}

window.closePOIModal = function () {
    const modal = document.getElementById('poi-details-modal');
    if (modal) {
        modal.remove();
    }
    if (window._poiModalEscHandler) {
        document.removeEventListener('keydown', window._poiModalEscHandler);
        delete window._poiModalEscHandler;
    }
}

window.showCreatePOIModal = function (coordinates) {
    console.log('📍 Opening POI creation modal', coordinates);

    const modalHTML = `
        <div id="create-poi-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                <div class="flex items-center justify-between p-6 border-b border-slate-600">
                    <h2 class="text-xl font-semibold text-white">Create Point of Interest</h2>
                    <button onclick="closeCreatePOIModal()" class="text-slate-400 hover:text-white transition-colors">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                
                <form id="create-poi-form" class="p-6 space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                        <input type="text" id="poi-name" required 
                               class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-sky-500"
                               placeholder="Enter Point of Interest name">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                        <textarea id="poi-description" rows="3"
                                  class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-sky-500"
                                  placeholder="Enter description (optional)"></textarea>
                    </div>
                    
                    <div class="bg-slate-700/50 rounded-lg p-3">
                        <p class="text-sm text-slate-300">
                            <strong>Location:</strong> ${coordinates[1].toFixed(7)}, ${coordinates[0].toFixed(7)}
                        </p>
                    </div>
                    
                    <div class="flex justify-end space-x-3 pt-4 border-t border-slate-600 mt-4">
                        <button type="button" onclick="closeCreatePOIModal()" class="btn-secondary" style="min-width: 120px;">Cancel</button>
                        <button type="submit" class="btn-primary" style="min-width: 120px;">Create Point of Interest</button>
                    </div>
                </form>
            </div>
        </div>
    `;

    // Add modal to body
    const existingModal = document.getElementById('create-poi-modal');
    if (existingModal) {
        existingModal.remove();
    }
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Focus on name input
    setTimeout(() => {
        const nameInput = document.getElementById('poi-name');
        if (nameInput) {
            nameInput.focus();

            // Clear error styling when user types
            nameInput.addEventListener('input', () => {
                nameInput.classList.remove('border-red-500', 'ring-2', 'ring-red-500');
            });
        }
    }, 100);

    // Handle form submission
    document.getElementById('create-poi-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        console.log('📝 POI form submitted');

        const nameInput = document.getElementById('poi-name');
        const descInput = document.getElementById('poi-description');

        if (!nameInput) {
            console.error('❌ Name input not found!');
            showNotification('error', 'Form error: name input not found');
            return;
        }

        const name = nameInput.value.trim();
        const description = descInput ? descInput.value.trim() : '';

        console.log('Form data:', { name, description });

        if (!name) {
            showNotification('error', 'Please enter a Point of Interest name');
            nameInput.focus();
            return;
        }

        // Show loading state
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';

        try {
            const response = await fetch('/api/v1/pois/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    name: name,
                    description: description,
                    latitude: coordinates[1],
                    longitude: coordinates[0]
                })
            });

            const data = await response.json();
            console.log('API Response:', response.status, data);

            if (response.ok) {
                showNotification('success', 'Point of Interest created successfully!');
                closeCreatePOIModal();

                // Reload POIs to show the new one
                await loadAllPOIs();

                // Open the newly created POI modal
                // Handle both response formats (with/without success wrapper)
                const poiData = data.data || data;
                if (poiData && poiData.id) {
                    openPOIModal(poiData.id, true);
                }
            } else {
                // Handle different error response formats
                let errorMsg = 'Failed to create Point of Interest';
                if (data.error) {
                    errorMsg = data.error;
                } else if (data.name && Array.isArray(data.name)) {
                    errorMsg = `Name error: ${data.name[0]}`;
                } else if (data.detail) {
                    errorMsg = data.detail;
                } else if (data.message) {
                    errorMsg = data.message;
                }

                console.error('❌ POI creation failed:', errorMsg);
                showNotification('error', errorMsg);

                // If it's a duplicate name error, highlight the input
                if (errorMsg.toLowerCase().includes('already exists') || errorMsg.toLowerCase().includes('unique')) {
                    nameInput.classList.add('border-red-500', 'ring-2', 'ring-red-500');
                    nameInput.focus();
                    nameInput.select();
                }
            }
        } catch (error) {
            console.error('Error creating POI:', error);
            showNotification('error', 'Failed to create Point of Interest: ' + error.message);
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

window.closeCreatePOIModal = function () {
    const modal = document.getElementById('create-poi-modal');
    if (modal) {
        modal.remove();
    }
}

window.showDeletePOIConfirmModal = function (poiData) {
    console.log('🗑️ Opening POI delete confirmation', poiData);

    const modalHTML = `
        <div id="delete-poi-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                <div class="flex items-center justify-between p-6 border-b border-slate-600">
                    <h2 class="text-xl font-semibold text-white">Delete Point of Interest</h2>
                    <button onclick="closeDeletePOIModal()" class="text-slate-400 hover:text-white transition-colors">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                
                <div class="p-6">
                    <div class="mb-6">
                        <p class="text-slate-300 mb-2">Are you sure you want to delete this Point of Interest?</p>
                        <p class="text-white font-semibold text-lg">${poiData.name}</p>
                    </div>
                    
                    <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-4 mb-6">
                        <p class="text-red-200 text-sm">
                            <strong>Warning:</strong> This action cannot be undone.
                        </p>
                    </div>
                    
                    <div class="flex justify-end space-x-3">
                        <button onclick="closeDeletePOIModal()" class="btn-secondary" style="min-width: 120px;">Cancel</button>
                        <button onclick="confirmDeletePOI('${poiData.id}')" class="btn-danger" style="min-width: 120px;">
                            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                            </svg>
                            Delete Point of Interest
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Add modal to body
    const existingModal = document.getElementById('delete-poi-modal');
    if (existingModal) {
        existingModal.remove();
    }
    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

window.closeDeletePOIModal = function () {
    const modal = document.getElementById('delete-poi-modal');
    if (modal) {
        modal.remove();
    }
}

window.confirmDeletePOI = async function (poiId) {
    console.log(`🗑️ Deleting POI: ${poiId}`);

    try {
        const response = await fetch(`/api/v1/pois/${poiId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCSRFToken()
            },
            credentials: 'same-origin'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('success', 'Point of Interest deleted successfully');
            closeDeletePOIModal();
            closePOIModal(); // Close the details modal if open

            // Reload POIs to remove the deleted one
            await loadAllPOIs();
        } else {
            const errorMsg = data.error || 'Failed to delete Point of Interest';
            showNotification('error', errorMsg);
        }
    } catch (error) {
        console.error('Error deleting POI:', error);
        showNotification('error', 'Failed to delete Point of Interest');
    }
}

window.editPOI = function (poiId) {
    console.log(`✏️ Opening edit modal for POI: ${poiId}`);

    const poi = allPOIs.get(poiId);
    if (!poi) {
        showNotification('error', 'Point of Interest not found');
        return;
    }

    const modalHTML = `
        <div id="edit-poi-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full max-w-md">
                <div class="flex items-center justify-between p-6 border-b border-slate-600">
                    <h2 class="text-xl font-semibold text-white">Edit Point of Interest</h2>
                    <button onclick="closeEditPOIModal()" class="text-slate-400 hover:text-white transition-colors">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                
                <form id="edit-poi-form" class="p-6 space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                        <input type="text" id="edit-poi-name" required value="${poi.name}"
                               class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-sky-500">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                        <textarea id="edit-poi-description" rows="3"
                                  class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-sky-500">${poi.description || ''}</textarea>
                    </div>
                    
                    <div class="bg-slate-700/50 rounded-lg p-3">
                        <p class="text-sm text-slate-300">
                            <strong>Location:</strong> ${Number(poi.latitude).toFixed(7)}, ${Number(poi.longitude).toFixed(7)}
                        </p>
                    </div>
                    
                    <div class="flex justify-end space-x-3 pt-4 border-t border-slate-600 mt-4">
                        <button type="button" onclick="closeEditPOIModal()" class="btn-secondary" style="min-width: 120px;">Cancel</button>
                        <button type="submit" class="btn-primary" style="min-width: 120px;">Save Changes</button>
                    </div>
                </form>
            </div>
        </div>
    `;

    // Add modal to body
    const existingModal = document.getElementById('edit-poi-modal');
    if (existingModal) {
        existingModal.remove();
    }
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Clear error styling when user types
    setTimeout(() => {
        const nameInput = document.getElementById('edit-poi-name');
        if (nameInput) {
            nameInput.addEventListener('input', () => {
                nameInput.classList.remove('border-red-500', 'ring-2', 'ring-red-500');
            });
        }
    }, 100);

    // Handle form submission
    document.getElementById('edit-poi-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        console.log('📝 POI edit form submitted');

        const nameInput = document.getElementById('edit-poi-name');
        const descInput = document.getElementById('edit-poi-description');

        if (!nameInput) {
            console.error('❌ Name input not found!');
            showNotification('error', 'Form error: name input not found');
            return;
        }

        const name = nameInput.value.trim();
        const description = descInput ? descInput.value.trim() : '';

        console.log('Edit form data:', { name, description });

        if (!name) {
            showNotification('error', 'Please enter a Point of Interest name');
            nameInput.focus();
            return;
        }

        // Show loading state
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';

        try {
            const response = await fetch(`/api/v1/pois/${poiId}/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    name: name,
                    description: description
                })
            });

            const data = await response.json();
            console.log('API Response:', response.status, data);

            if (response.ok) {
                showNotification('success', 'Point of Interest updated successfully!');
                closeEditPOIModal();
                closePOIModal(); // Close the details modal

                // Reload POIs to show the updated one
                await loadAllPOIs();

                // Reopen the POI modal with updated data
                openPOIModal(poiId);
            } else {
                // Handle different error response formats
                let errorMsg = 'Failed to update Point of Interest';
                if (data.error) {
                    errorMsg = data.error;
                } else if (data.name && Array.isArray(data.name)) {
                    errorMsg = `Name error: ${data.name[0]}`;
                } else if (data.detail) {
                    errorMsg = data.detail;
                } else if (data.message) {
                    errorMsg = data.message;
                }

                console.error('❌ POI update failed:', errorMsg);
                showNotification('error', errorMsg);

                // If it's a duplicate name error, highlight the input
                if (errorMsg.toLowerCase().includes('already exists') || errorMsg.toLowerCase().includes('unique')) {
                    nameInput.classList.add('border-red-500', 'ring-2', 'ring-red-500');
                    nameInput.focus();
                    nameInput.select();
                }
            }
        } catch (error) {
            console.error('Error updating POI:', error);
            showNotification('error', 'Failed to update Point of Interest: ' + error.message);
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

window.closeEditPOIModal = function () {
    const modal = document.getElementById('edit-poi-modal');
    if (modal) {
        modal.remove();
    }
} 