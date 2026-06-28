import { initColorPicker } from '../../frontend_private/static/private/js/color-picker.js';
import { attachTaggedEntityList } from '../../frontend_private/static/private/js/forms/tagged_entity_list.js';
import { FormModals } from '../../frontend_private/static/private/js/forms/modals.js';
import { GPXImport } from '../../frontend_private/static/private/js/gpx_import.js';
import { escapeHtml, safeCssColor } from '../../frontend_private/static/private/js/xss-helpers.js';

export function init(context) {
    let allTracks = [];  // kept in sync by renderList

        GPXImport.init(context.csrfToken);
        $('#import-gpx-button').on('click', () => GPXImport.showModal());
        $(document).on('click', '[data-gpx-action]', function () {
            const actions = {
                browse: () => document.getElementById('gpx-file-input').click(),
                clear: () => GPXImport.clearFile(),
                hide: () => GPXImport.hideModal(),
                upload: () => GPXImport.upload(),
                'hide-warning': () => GPXImport.hideWarningModal(),
            };
            actions[$(this).data('gpx-action')]?.();
        });

        // Format date for display
        function formatDate(dateString) {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', { 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        }

        // Render tracks in table and cards
        function renderTracks(tracks) {
            allTracks = tracks;
            const tableBody = $('#tracks-table-body');
            const cardsContainer = $('#tracks-cards-container');

            if (allTracks.length === 0) {
                const emptyStateHtml = `
                    <svg class="w-16 h-16 center-x mb-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
                    </svg>
                    <p class="text-lg font-medium">No GPS tracks yet</p>
                    <p class="text-sm mt-1">Import a GPX file to add your first GPS track</p>
                `;
                
                tableBody.html(`
                    <tr>
                        <td colspan="4" class="px-2 py-8 text-center text-slate-400">
                            ${emptyStateHtml}
                        </td>
                    </tr>
                `);
                cardsContainer.html(`
                    <div class="text-center py-12 text-slate-400">
                        ${emptyStateHtml}
                    </div>
                `);
                return;
            }

            // Render table rows
            let tableHtml = '';
            allTracks.forEach((track, index) => {
                tableHtml += `
                    <tr>
                        <td class="px-2 first:pl-5 last:pr-5 py-3">
                            <div class="text-center font-medium text-slate-100">${index + 1}</div>
                        </td>
                        <td class="px-2 first:pl-5 last:pr-5 py-3">
                            <div class="flex items-center gap-3">
                                <div class="w-3 h-3 rounded-full shrink-0" style="background-color: ${safeCssColor(track.color, '#94a3b8')}"></div>
                                <div class="font-medium text-slate-100">${escapeHtml(track.name)}</div>
                            </div>
                        </td>
                        <td class="px-2 first:pl-5 last:pr-5 py-3">
                            <div class="text-center text-slate-400 text-sm">
                                ${formatDate(track.creation_date)}
                            </div>
                        </td>
                        <td class="px-2 first:pl-5 last:pr-5 py-3">
                            <div class="flex items-center justify-center gap-2">
                                <!-- Edit Button -->
                                <button class="btn-edit-track cursor-pointer" data-track-id="${track.id}" title="Edit track name">
                                    <svg class="h-6 w-6 stroke-current text-amber-500 hover:text-amber-400" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                                        <path stroke="none" d="M0 0h24v24H0z" fill="none" />
                                        <path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4" />
                                        <path d="M13.5 6.5l4 4" />
                                    </svg>
                                </button>
                                <!-- Delete Button -->
                                <button class="btn-delete-track cursor-pointer" data-track-id="${track.id}" title="Delete track">
                                    <svg class="h-6 w-6 stroke-current text-rose-500 hover:text-rose-400" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                                        <path stroke="none" d="M0 0h24v24H0z" fill="none" />
                                        <path d="M18 6l-12 12" />
                                        <path d="M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            });
            tableBody.html(tableHtml);

            // Render mobile cards
            let cardsHtml = '';
            allTracks.forEach(track => {
                cardsHtml += `
                    <div class="track-card">
                        <div class="track-card-header">
                            <div class="track-card-title flex items-center gap-3">
                                <div class="w-4 h-4 rounded-full shrink-0" style="background-color: ${safeCssColor(track.color, '#94a3b8')}"></div>
                                <div class="text-lg font-semibold text-slate-100">${escapeHtml(track.name)}</div>
                            </div>
                            <div class="track-card-actions">
                                <button class="btn-edit-track w-10 h-10 shrink-0 flex items-center justify-center bg-amber-600 hover:bg-amber-500 rounded-full transition" data-track-id="${track.id}">
                                    <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor">
                                        <path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4" />
                                        <path d="M13.5 6.5l4 4" />
                                    </svg>
                                </button>
                                <button class="btn-delete-track w-10 h-10 shrink-0 flex items-center justify-center bg-rose-600 hover:bg-rose-500 rounded-full transition" data-track-id="${track.id}">
                                    <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor">
                                        <path d="M18 6l-12 12" />
                                        <path d="M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                        <div class="track-card-body">
                            <div class="track-card-row">
                                <span class="track-card-label">Created</span>
                                <span class="track-card-value">${formatDate(track.creation_date)}</span>
                            </div>
                        </div>
                    </div>
                `;
            });
            cardsContainer.html(cardsHtml);

            // Attach event handlers
            attachEventHandlers();
        }

        // Attach event handlers to dynamically created elements
        function attachEventHandlers() {
            $('.btn-edit-track').off('click').on('click', function() {
                listApi.openEditModal($(this).data('track-id'));
            });

            $('.btn-delete-track').off('click').on('click', function() {
                listApi.openDeleteModal($(this).data('track-id'));
            });
        }

        // Track color picker helpers
        var setTrackColor = initColorPicker({
            preview:      '#edit-track-color-preview',
            hiddenInput:  '#edit-track-color-value',
            nativePicker: '#edit-track-color-picker',
            pickerBtn:    '#edit-track-color-picker-btn',
            hexInput:     '#edit-track-color-hex',
            presets:      '.edit-track-color-preset',
        });

        const listApi = attachTaggedEntityList({
            listEndpoint: context.listEndpoint,
            detailEndpointBuilder: function (id) { return Urls['api:v2:gps-track-detail'](id); },
            editMethod: 'PATCH',

            renderList: renderTracks,

            entityLabel: 'GPS track',
            loadFailedMessage: 'Error loading GPS tracks',

            editFormSelector: '#edit-track-form',
            editIdInputSelector: '#edit-track-id',
            editModalSelector: '#edit-track-modal',
            closeEditModalSelectors: '.btn-close-edit-modal',

            deleteModalSelector: '#delete-track-modal',
            deleteIdInputSelector: '#delete-track-id',
            confirmDeleteSelector: '#btn-confirm-delete',
            closeDeleteModalSelectors: '.btn-close-delete-modal',

            openEditModalForEntity: function (track) {
                $('#edit-track-id').val(track.id);
                $('#edit-track-name').val(track.name);
                setTrackColor(track.color || '#94a3b8');
            },
            openDeleteModalForEntity: function (track) {
                $('#delete-track-info').html(
                    '<div class="flex items-center gap-2 bg-srgb-slate-700-50 rounded-lg p-3">' +
                    '  <div class="track-icon">' +
                    '    <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                    '      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>' +
                    '    </svg>' +
                    '  </div>' +
                    '  <span class="text-slate-100 font-medium">' + escapeHtml(track.name) + '</span>' +
                    '</div>'
                );
            },
            collectEditPayload: function () {
                const name = $('#edit-track-name').val().trim();
                const color = $('#edit-track-color-value').val();
                if (!name) { FormModals.showError('Please enter a track name'); return null; }
                return { name: name, color: color };
            },
        });

        // Listen for GPX import event to refresh tracks
        window.addEventListener('speleo:refresh-gps-tracks', function() {
            listApi.reload();
        });
}
