export function init(context) {
    let fieldCounter = 0;
        const textarea = document.getElementById(context.textareaId);
        const container = document.getElementById('custom-fields-container');
        const noFieldsMsg = document.getElementById('no-fields-msg');
        const addBtn = document.getElementById('add-field-btn');

        // Mandatory field slugs (must match MandatoryFieldSlug enum)
        const MANDATORY_SLUGS = ['measurement_date', 'submitter_email'];

        function isMandatorySlug(slug) {
            return MANDATORY_SLUGS.includes(slug);
        }

        // Load existing fields
        function loadExistingFields() {
            try {
                const data = JSON.parse(textarea.value || '{}');
                // Filter out mandatory fields and load custom ones
                // Mandatory fields are identified by slug, not a 'mandatory' property
                for (const [slug, fieldData] of Object.entries(data)) {
                    if (!isMandatorySlug(slug)) {
                        addFieldElement(fieldData, slug, true); // true = existing field (immutable)
                    }
                }
                updateNoFieldsMsg();
            } catch (e) {
                console.error('Error parsing existing fields:', e);
            }
        }

        // Update visibility of "no fields" message
        function updateNoFieldsMsg() {
            if (container.children.length === 0) {
                noFieldsMsg.style.display = 'block';
            } else {
                noFieldsMsg.style.display = 'none';
            }
        }

        // Save fields to textarea
        // Note: Slug generation and hashing are done server-side by the model's save() method
        function saveFields() {
            let existingData = {};
            const fields = {};

            // Load existing fields from textarea to preserve slugs and hashes
            try {
                existingData = JSON.parse(textarea.value || '{}');
                // Preserve mandatory fields and their slugs/hashes (identified by slug, not 'mandatory' property)
                for (const slug of MANDATORY_SLUGS) {
                    if (existingData[slug]) {
                        fields[slug] = existingData[slug];
                    }
                }
            } catch (e) {
                // If no existing data, fields object stays empty
            }

            // Process each field div
            for (const fieldDiv of Array.from(container.children)) {
                const isExisting = fieldDiv.dataset.isExisting === 'true';
                const existingSlug = fieldDiv.dataset.slug;

                const nameInput = fieldDiv.querySelector('.field-name');
                const typeSelect = fieldDiv.querySelector('.field-type');
                const requiredCheck = fieldDiv.querySelector('.field-required');
                const optionsInput = fieldDiv.querySelector('.field-options');

                // Skip fields without a valid type selected
                if (!typeSelect.value || !nameInput.value.trim()) {
                    continue;
                }

                const fieldData = {
                    name: nameInput.value.trim(),
                    type: typeSelect.value,
                    required: requiredCheck.checked
                };

                if (typeSelect.value === 'select' && optionsInput && optionsInput.value) {
                    fieldData.options = optionsInput.value.split(',').map(o => o.trim()).filter(o => o);
                }

                if (isExisting && existingSlug && existingData[existingSlug]) {
                    // Preserve existing slug and hash (immutable)
                    // Backend will verify hash matches
                    fields[existingSlug] = Object.assign({}, existingData[existingSlug], fieldData);
                } else {
                    // New field - use temporary slug for JSON structure
                    // Backend model's save() method must process temp slugs and generate proper slugs/hashes
                    const tempSlug = 'temp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                    fields[tempSlug] = fieldData;
                }
            }

            textarea.value = JSON.stringify(fields, null, 2);
        }

        // Create field element
        function addFieldElement(existingField = null, existingSlug = null, isExisting = false) {
            fieldCounter++;
            const fieldDiv = document.createElement('div');
            fieldDiv.className = 'exp-field-item';
            fieldDiv.dataset.isExisting = isExisting;
            if (existingSlug) {
                fieldDiv.dataset.slug = existingSlug;
            }

            const name = existingField?.name || '';
            const type = existingField?.type || 'text';
            const required = existingField?.required || false;
            const options = existingField?.options?.join(', ') || '';

            // Lock icon for existing fields
            const lockIcon = isExisting ? '🔒 ' : '';
            const disabledAttr = isExisting ? 'disabled' : '';
            const readonlyAttr = isExisting ? 'readonly' : '';
            const lockedClass = isExisting ? 'style="opacity: 0.7;"' : '';

            const slugDisplay = existingSlug ? `<code style="font-family: monospace; background: var(--darkened-bg, #e5e7eb); padding: 2px 6px; border-radius: 3px; font-size: 11px;">Slug: ${existingSlug}</code>` : '';

            fieldDiv.innerHTML = `
                ${isExisting ? '<div style="background: var(--selected-bg, #79aec8); color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; margin-bottom: 8px; display: inline-block;">🔒 IMMUTABLE FIELD - Cannot be modified or removed ' + slugDisplay + '</div>' : ''}
                <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 12px; align-items: start;" ${lockedClass}>
                    <div>
                        <label>
                            ${lockIcon}Field Name <span class="exp-required">*</span>
                        </label>
                        <input type="text" class="field-name" value="${name}"
                               placeholder="e.g., Water Quality, pH Level"
                               ${readonlyAttr}>
                        ${!isExisting ? '<div style="font-size: 11px; color: var(--body-quiet-color, #999); margin-top: 2px;">Slug will be auto-generated</div>' : ''}
                    </div>

                    <div>
                        <label>
                            ${lockIcon}Field Type <span class="exp-required">*</span>
                        </label>
                        <select class="field-type" ${disabledAttr} ${!isExisting ? 'required' : ''}>
                            ${isExisting
                                ? ''
                                : '<option value="" selected disabled>Select a value</option>'
                            }
                            <option value="text" ${type === 'text' ? 'selected' : ''}>Text</option>
                            <option value="number" ${type === 'number' ? 'selected' : ''}>Number</option>
                            <option value="date" ${type === 'date' ? 'selected' : ''}>Date</option>
                            <option value="boolean" ${type === 'boolean' ? 'selected' : ''}>Yes/No</option>
                            <option value="select" ${type === 'select' ? 'selected' : ''}>Multiple Choices</option>
                        </select>
                    </div>

                    <div style="display: flex; gap: 8px; align-items: end; padding-top: 24px;">
                        <label style="display: flex; align-items: center; font-size: 13px; white-space: nowrap; color: var(--body-fg, #333);">
                            <input type="checkbox" class="field-required" ${required ? 'checked' : ''}
                                   ${disabledAttr} style="margin-right: 4px;">
                            Required
                        </label>
                        ${isExisting
                            ? '<span style="color: var(--body-quiet-color, #999); font-size: 12px; padding: 8px 12px;">🔒 Locked</span>'
                            : '<button type="button" class="remove-btn exp-remove-btn">✕ Remove</button>'
                        }
                    </div>
                </div>

                <div class="options-container" style="margin-top: 12px; ${type === 'select' ? '' : 'display: none;'}">
                    <label>
                        ${lockIcon}Options (comma-separated)
                    </label>
                    <input type="text" class="field-options" value="${options}"
                           placeholder="e.g., Low, Medium, High"
                           ${readonlyAttr}>
                </div>
            `;

            container.appendChild(fieldDiv);

            // Event listeners only for new fields
            if (!isExisting) {
                const removeBtn = fieldDiv.querySelector('.remove-btn');
                removeBtn.addEventListener('click', () => {
                    fieldDiv.remove();
                    updateNoFieldsMsg();
                    saveFields();
                });

                const typeSelect = fieldDiv.querySelector('.field-type');
                const optionsContainer = fieldDiv.querySelector('.options-container');
                typeSelect.addEventListener('change', (e) => {
                    optionsContainer.style.display = e.target.value === 'select' ? 'block' : 'none';
                    saveFields();
                });

                // Auto-save on changes
                fieldDiv.querySelectorAll('input, select').forEach(el => {
                    el.addEventListener('change', saveFields);
                    el.addEventListener('input', saveFields);
                });
            }
        }

        // Add field button
        addBtn.addEventListener('click', () => {
            addFieldElement();
            updateNoFieldsMsg();
            saveFields();
        });

        // Initialize
        loadExistingFields();
}
