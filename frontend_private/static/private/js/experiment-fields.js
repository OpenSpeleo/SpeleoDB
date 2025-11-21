/**
 * Experiment Fields Manager
 * Handles dynamic field creation, tag management, and Title Case conversion
 * for experiment custom fields with Multiple Choice options
 */

(function ($) {
    'use strict';

    // Field counter for unique IDs
    let fieldCounter = 0;

    /**
     * Convert text to Title Case
     * Standardizes values to make them case-agnostic
     */
    function toTitleCase(str) {
        return str.replace(
            /\w\S*/g,
            text => text.charAt(0).toUpperCase() + text.substring(1).toLowerCase()
        );
    }

    /**
     * Toggle visibility of "no fields" message
     */
    function toggleNoFieldsMessage() {
        const customFieldsContainer = $('#custom_fields_container');
        const noFieldsMessage = $('#no_fields_message');

        if (customFieldsContainer.children().length === 0) {
            noFieldsMessage.show();
        } else {
            noFieldsMessage.hide();
        }
    }

    /**
     * Create a tag element with Title Case text
     * Tags are used for Multiple Choice field options
     */
    function createTag(text, container) {
        const titleCaseText = toTitleCase(text);
        const tag = $(`
            <span class="inline-flex items-center gap-1 px-3 py-1 bg-indigo-500 bg-opacity-20 border border-indigo-500 text-indigo-100 rounded-full text-sm">
                <span class="tag-text">${titleCaseText}</span>
                <button type="button" class="remove-tag hover:text-rose-400 transition-colors">
                    <svg class="w-3 h-3 fill-current" viewBox="0 0 16 16">
                        <path d="M12.72 3.293a1 1 0 00-1.415 0L8 6.586 4.695 3.293a1 1 0 00-1.414 1.414L6.586 8l-3.305 3.305a1 1 0 101.414 1.414L8 9.414l3.305 3.305a1 1 0 001.414-1.414L9.414 8l3.305-3.293a1 1 0 000-1.414z"/>
                    </svg>
                </button>
            </span>
        `);
        container.append(tag);
    }

    /**
     * Create a new field element with all necessary inputs
     */
    function createFieldElement(fieldId) {
        return `
            <div class="bg-slate-700 rounded-lg p-4 border border-slate-600 field-item" data-field-id="${fieldId}">
                <div class="flex flex-col gap-3">
                    <div class="flex flex-col sm:flex-row gap-3">
                        <div class="flex-1">
                            <label class="block text-xs font-medium text-slate-400 mb-1">Field Name<span class="text-rose-600"> *</span></label>
                            <input type="text" 
                                   class="form-input w-full field-name" 
                                   placeholder="e.g., pH Level, Water Hardness" 
                                   required />
                        </div>
                        <div class="flex-1">
                            <div class="flex flex-col sm:flex-row gap-3">
                                <div class="flex-1">
                                    <label class="block text-xs font-medium text-slate-400 mb-1">Field Type<span class="text-rose-600"> *</span></label>
                                    <select class="form-select w-full field-type" required>
                                        <option value="" selected disabled>Select a value</option>
                                        <option value="text">Text</option>
                                        <option value="number">Number</option>
                                        <option value="date">Date</option>
                                        <option value="boolean">Yes/No</option>
                                        <option value="select">Multiple Choices</option>
                                    </select>
                                </div>
                                <div class="flex-1">
                                    <label class="block text-xs font-medium text-slate-400 mb-1">Field is Required</label>
                                    <label class="flex items-center">
                                        <input type="checkbox" class="form-checkbox field-required" />
                                        <span class="text-sm ml-2 text-slate-300">Required</span>
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Options section for Multiple Choices -->
                    <div class="field-options-container hidden">
                        <label class="block text-xs font-medium text-slate-400 mb-2">Available Options</label>
                        <div class="flex gap-2 mb-2">
                            <input type="text" 
                                   class="form-input flex-1 field-option-input text-sm" 
                                   placeholder="Type an option and press Enter or comma" />
                        </div>
                        <div class="flex flex-wrap gap-2 field-tags-container min-h-[2rem]">
                            <!-- Tags will be added here -->
                        </div>
                    </div>
                    
                    <div class="flex justify-end">
                        <button type="button" 
                                class="btn-sm bg-rose-500 hover:bg-rose-600 text-white remove-field-btn"
                                data-field-id="${fieldId}">
                            <svg class="w-4 h-4 fill-current shrink-0 inline-block mr-1" viewBox="0 0 16 16">
                                <path d="M5 7h6v2H5V7zm7-4H4v2h8V3zM6 12h4v2H6v-2z" />
                            </svg>
                            Remove Field
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Check for duplicate field names (case-insensitive)
     * Also checks against existing fields (for edit mode)
     * Returns array of duplicate field IDs
     */
    function checkDuplicateFieldNames() {
        const fieldNames = new Map(); // Map of lowercase name -> array of field IDs
        const duplicates = new Set();
        const existingNames = new Set();

        // Collect existing field names (read-only fields in edit mode)
        $('.existing-field-item').each(function () {
            const existingName = $(this).data('field-name');
            if (existingName) {
                existingNames.add(toTitleCase(existingName).toLowerCase());
            }
        });

        // Check new fields
        $('.field-item').each(function () {
            const fieldId = $(this).data('field-id');
            const fieldName = $(this).find('.field-name').val().trim();

            if (fieldName) {
                const normalizedName = toTitleCase(fieldName);
                const lowerName = normalizedName.toLowerCase();

                // Check against existing fields
                if (existingNames.has(lowerName)) {
                    duplicates.add(fieldId);
                }

                if (!fieldNames.has(lowerName)) {
                    fieldNames.set(lowerName, []);
                }
                fieldNames.get(lowerName).push(fieldId);
            }
        });

        // Find duplicates among new fields
        fieldNames.forEach((fieldIds, name) => {
            if (fieldIds.length > 1) {
                fieldIds.forEach(id => duplicates.add(id));
            }
        });

        return Array.from(duplicates);
    }

    /**
     * Highlight duplicate fields with error styling
     */
    function highlightDuplicateFields(duplicateIds) {
        // Clear all previous errors
        $('.field-name').removeClass('border-rose-500 hover:border-rose-500 border-2');

        // Highlight duplicates
        duplicateIds.forEach(fieldId => {
            $(`.field-item[data-field-id="${fieldId}"] .field-name`)
                .addClass('border-rose-500 hover:border-rose-500 border-2');
        });
    }

    /**
     * Validate all field names are unique
     * Returns true if valid, false if duplicates found
     */
    function validateUniqueFieldNames() {
        const duplicates = checkDuplicateFieldNames();

        if (duplicates.length > 0) {
            highlightDuplicateFields(duplicates);
            return false;
        }

        // Clear any previous error highlighting
        $('.field-name').removeClass('border-rose-500 border-2');
        return true;
    }

    /**
     * Initialize all event handlers for experiment fields
     */
    function initializeExperimentFields() {
        // Add field button
        $('#add_field_btn').click(function (e) {
            e.preventDefault();
            fieldCounter++;
            const fieldElement = createFieldElement(fieldCounter);
            $('#custom_fields_container').append(fieldElement);
            toggleNoFieldsMessage();
        });

        // Remove field button (delegated)
        $(document).on('click', '.remove-field-btn', function (e) {
            e.preventDefault();
            const fieldId = $(this).data('field-id');
            $(`.field-item[data-field-id="${fieldId}"]`).remove();
            toggleNoFieldsMessage();
            // Revalidate after removal
            validateUniqueFieldNames();
        });

        // Titleize field name on blur and validate uniqueness
        $(document).on('blur', '.field-name', function () {
            const input = $(this);
            const value = input.val().trim();

            if (value) {
                // Apply Title Case
                const titleCased = toTitleCase(value);
                input.val(titleCased);

                // Validate uniqueness
                validateUniqueFieldNames();
            }
        });

        // Show/hide options when field type changes
        $(document).on('change', '.field-type', function () {
            const container = $(this).closest('.field-item');
            const optionsContainer = container.find('.field-options-container');

            if ($(this).val() === 'select') {
                optionsContainer.removeClass('hidden');
            } else {
                optionsContainer.addClass('hidden');
            }
        });

        // Handle Enter key and comma for tag creation
        $(document).on('keydown', '.field-option-input', function (e) {
            const input = $(this);
            const value = input.val().trim();
            const container = input.closest('.field-options-container').find('.field-tags-container');

            if (e.key === ',' || e.key === 'Enter') {
                e.preventDefault();

                // During keydown, comma hasn't been added yet
                const optionValue = value;

                if (optionValue && optionValue !== ',') {
                    // Check if tag already exists (case-insensitive)
                    let exists = false;
                    container.find('.tag-text').each(function () {
                        if ($(this).text().toLowerCase() === optionValue.toLowerCase()) {
                            exists = true;
                        }
                    });

                    if (!exists) {
                        createTag(optionValue, container);
                    }
                    input.val('');
                }
            }
        });

        // Handle comma in input for paste operations
        $(document).on('input', '.field-option-input', function (e) {
            const input = $(this);
            const value = input.val();
            const container = input.closest('.field-options-container').find('.field-tags-container');

            if (value.includes(',')) {
                const parts = value.split(',').map(p => p.trim()).filter(p => p);

                parts.forEach(part => {
                    // Check if tag already exists (case-insensitive)
                    let exists = false;
                    container.find('.tag-text').each(function () {
                        if ($(this).text().toLowerCase() === part.toLowerCase()) {
                            exists = true;
                        }
                    });

                    if (!exists) {
                        createTag(part, container);
                    }
                });

                input.val('');
            }
        });

        // Remove tag
        $(document).on('click', '.remove-tag', function (e) {
            e.preventDefault();
            $(this).closest('span').remove();
        });

        // Initialize visibility
        toggleNoFieldsMessage();

        // Hide modals on body click
        $("body").click(function () {
            if ($("#modal_success").is(":visible")) {
                $("#modal_success").hide();
            }
            if ($("#modal_error").is(":visible")) {
                $("#modal_error").hide();
            }
        });
    }

    // Export to global scope for use in templates
    window.ExperimentFields = {
        initialize: initializeExperimentFields,
        toTitleCase: toTitleCase,
        validateUniqueFieldNames: validateUniqueFieldNames
    };

})(jQuery);

