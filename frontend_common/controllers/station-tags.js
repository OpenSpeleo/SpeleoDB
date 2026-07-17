import { attachTaggedEntityList } from '../../frontend_private/static/private/js/forms/tagged_entity_list.js';
import { FormModals } from '../../frontend_private/static/private/js/forms/modals.js';
import { escapeHtml, safeCssColor } from '../../frontend_private/static/private/js/xss-helpers.js';

export function init(context) {
    const predefinedColors = [
            "#ef4444", "#f97316", "#f59e0b", "#eab308", "#84cc16",
            "#22c55e", "#10b981", "#14b8a6", "#06b6d4", "#0ea5e9",
            "#3b82f6", "#6366f1", "#8b5cf6", "#a855f7", "#d946ef",
            "#ec4899", "#f43f5e", "#fb7185", "#fb923c", "#facc15"
        ];

        let allTags = [];  // mirror updated by renderList()

        // Render tags in table and cards
        function renderTags(tags) {
            allTags = tags;
            const tableBody = $('#tags-table-body');
            const cardsContainer = $('#tags-cards-container');

            if (allTags.length === 0) {
                tableBody.html(`
                    <tr>
                        <td colspan="6" class="px-2 py-8 text-center text-slate-400">
                            <svg class="w-16 h-16 center-x mb-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"></path>
                            </svg>
                            <p class="text-lg font-medium">No tags yet</p>
                            <p class="text-sm mt-1">Create your first tag to start organizing stations</p>
                        </td>
                    </tr>
                `);
                cardsContainer.html(`
                    <div class="text-center py-12 text-slate-400">
                        <svg class="w-16 h-16 center-x mb-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"></path>
                        </svg>
                        <p class="text-lg font-medium">No tags yet</p>
                        <p class="text-sm mt-1">Create your first tag to start organizing stations</p>
                    </div>
                `);
                return;
            }

            // Render table rows
            let tableHtml = '';
            allTags.forEach((tag, index) => {
                tableHtml += `
                    <tr>
                        <td class="px-2 first:pl-5 last:pr-5 py-3">
                            <div class="text-center font-medium text-slate-100">${index + 1}</div>
                        </td>
                        <td class="px-2 first:pl-5 last:pr-5 py-3">
                            <div class="font-medium text-slate-100">${escapeHtml(tag.name)}</div>
                        </td>
                        <td class="px-2 first:pl-5 last:pr-5 py-3">
                            <div class="flex items-center justify-center gap-2">
                                <span class="color-swatch" style="background-color: ${safeCssColor(tag.color)}"></span>
                                <code class="text-xs text-slate-400">${escapeHtml(tag.color)}</code>
                            </div>
                        </td>
                        <td class="px-2 first:pl-5 last:pr-5 py-3">
                            <div class="text-center">
                                <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-700">
                                    ${tag.station_count || 0}
                                </span>
                            </div>
                        </td>
                        <td class="px-2 first:pl-5 last:pr-5 py-3">
                            <div class="text-center text-slate-400 text-xs">
                                ${new Date(tag.creation_date).toLocaleDateString('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\//g, '/')}
                            </div>
                        </td>
                        <td class="px-2 first:pl-5 last:pr-5 py-3">
                            <div class="flex items-center justify-center gap-2">
                                <!-- Edit Button -->
                                <button class="btn-edit-tag cursor-pointer" data-tag-id="${tag.id}">
                                    <svg class="h-6 w-6 stroke-current text-amber-500 hover:text-amber-400" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                                        <path stroke="none" d="M0 0h24v24H0z" fill="none" />
                                        <path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4" />
                                        <path d="M13.5 6.5l4 4" />
                                    </svg>
                                </button>
                                <!-- Delete Button -->
                                <button class="btn-delete-tag cursor-pointer" data-tag-id="${tag.id}">
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
            allTags.forEach(tag => {
                cardsHtml += `
                    <div class="tag-card">
                        <div class="tag-card-header">
                            <div class="tag-card-title flex items-center gap-3">
                                <span class="color-swatch" style="background-color: ${safeCssColor(tag.color)}"></span>
                                <div>
                                    <div class="text-lg font-semibold text-slate-100">${escapeHtml(tag.name)}</div>
                                    <div class="text-xs text-slate-400">${tag.station_count || 0} station${(tag.station_count || 0) !== 1 ? 's' : ''}</div>
                                </div>
                            </div>
                            <div class="tag-card-actions">
                                <button class="btn-edit-tag w-10 h-10 shrink-0 flex items-center justify-center bg-amber-600 hover:bg-amber-500 rounded-full transition" data-tag-id="${tag.id}">
                                    <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor">
                                        <path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4" />
                                        <path d="M13.5 6.5l4 4" />
                                    </svg>
                                </button>
                                <button class="btn-delete-tag w-10 h-10 shrink-0 flex items-center justify-center bg-rose-600 hover:bg-rose-500 rounded-full transition" data-tag-id="${tag.id}">
                                    <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor">
                                        <path d="M18 6l-12 12" />
                                        <path d="M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                        <div class="tag-card-body">
                            <div class="tag-card-row">
                                <span class="tag-card-label">Color</span>
                                <span class="tag-card-value"><code>${escapeHtml(tag.color)}</code></span>
                            </div>
                            <div class="tag-card-row">
                                <span class="tag-card-label">Created</span>
                                <span class="tag-card-value">${new Date(tag.creation_date).toLocaleDateString()}</span>
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
            $('.btn-edit-tag').off('click').on('click', function() {
                listApi.openEditModal($(this).data('tag-id'));
            });

            $('.btn-delete-tag').off('click').on('click', function() {
                listApi.openDeleteModal($(this).data('tag-id'));
            });
        }

        // Populate color picker
        function populateColorPicker(selectedColor) {
            const picker = $('#edit-tag-color-picker');
            let html = '';

            // Normalize selected color for comparison (case-insensitive)
            const normalizedSelected = selectedColor ? selectedColor.toUpperCase() : null;

            predefinedColors.forEach(color => {
                const isSelected = color.toUpperCase() === normalizedSelected ? 'selected' : '';
                html += `
                    <div class="tag-color-picker-option ${isSelected}"
                         style="background-color: ${color}"
                         data-color="${color}"
                         title="${color}"></div>
                `;
            });

            picker.html(html);

            // Attach click handlers
            $('.tag-color-picker-option').off('click').on('click', function() {
                const color = $(this).data('color');
                selectColor(color);
            });

            // Set initial color
            if (selectedColor) {
                $('#edit-tag-color').val(selectedColor);
                $('#custom-color-input').val(selectedColor);
            } else {
                selectColor(predefinedColors[0]);
            }
        }

        // Select color
        function selectColor(color) {
            $('#edit-tag-color').val(color);
            $('.tag-color-picker-option').removeClass('selected');
            // Case-insensitive color matching
            $('.tag-color-picker-option').each(function() {
                if ($(this).data('color').toUpperCase() === color.toUpperCase()) {
                    $(this).addClass('selected');
                }
            });
            // Update custom color input to match
            $('#custom-color-input').val(color);
        }

        // Use custom color from color picker (auto-triggered on change)
        function useCustomColor() {
            const customColorInput = document.getElementById('custom-color-input');
            if (!customColorInput) { return; }
            const customColor = customColorInput.value.toUpperCase();
            $('#edit-tag-color').val(customColor);
            $('.tag-color-picker-option').removeClass('selected');
        }
        $('#custom-color-input').on('change', useCustomColor);

        const listApi = attachTaggedEntityList({
            listEndpoint: context.listEndpoint,
            detailEndpointBuilder: function (id) { return Urls['api:v2:station-tag-detail'](id); },
            editMethod: 'PUT',

            renderList: renderTags,

            entityLabel: 'tag',
            loadFailedMessage: 'Error loading tags',

            editFormSelector: '#edit-tag-form',
            editIdInputSelector: '#edit-tag-id',
            editModalSelector: '#edit-tag-modal',
            editModalTitleSelector: '#edit-modal-title',
            createModalTitle: 'Create New Tag',
            editModalTitle: 'Edit Tag',
            createBtnSelector: '#btn-create-tag',
            closeEditModalSelectors: '.btn-close-edit-modal',
            createSubmitLabelSelector: '#edit-submit-text',
            createSubmitLabel: 'Create Tag',
            editSubmitLabel: 'Save Changes',

            deleteModalSelector: '#delete-tag-modal',
            deleteIdInputSelector: '#delete-tag-id',
            confirmDeleteSelector: '#btn-confirm-delete',
            closeDeleteModalSelectors: '.btn-close-delete-modal',

            resetEditModal: function () {
                populateColorPicker(null);
            },
            openEditModalForEntity: function (tag) {
                $('#edit-tag-id').val(tag.id);
                $('#edit-tag-name').val(tag.name);
                $('#edit-tag-color').val(tag.color);
                populateColorPicker(tag.color);
            },
            openDeleteModalForEntity: function (tag) {
                $('#delete-tag-info').html(
                    '<div class="flex items-center gap-2 bg-srgb-slate-700-50 rounded-lg p-3">' +
                    '  <span class="color-swatch" style="background-color: ' + safeCssColor(tag.color) + '"></span>' +
                    '  <span class="text-slate-100 font-medium">' + escapeHtml(tag.name) + '</span>' +
                    '</div>'
                );
                $('#delete-tag-station-count').text(tag.station_count || 0);
            },
            collectEditPayload: function () {
                const name = $('#edit-tag-name').val().trim();
                const color = $('#edit-tag-color').val();
                if (!name) { FormModals.showError('Please enter a tag name'); return null; }
                if (!color) { FormModals.showError('Please select a color'); return null; }
                if (!/^#[0-9A-Fa-f]{6}$/.test(color)) {
                    FormModals.showError('Invalid color format. Please use hex format (#RRGGBB)');
                    return null;
                }
                return { name: name, color: color };
            },
        });
}
