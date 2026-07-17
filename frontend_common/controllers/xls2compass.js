import { attachSurveyTableTool } from '../../frontend_private/static/private/js/forms/survey_table_tool.js';
import { escapeHtml } from '../../frontend_private/static/private/js/xss-helpers.js';

export function init(context) {
    const COLUMNS = ["station", "depth", "length", "azimuth", "left", "right", "up", "down", "flags", "comment"];
        const $tbody = $('#dataTable tbody');
        const $statusEl = $('#status');

        // Survey Team Tags
        const surveyTeamMembers = [];
        const $teamContainer = $('#surveyTeamContainer');
        const $teamInput = $('#surveyTeamInput');

        $(window).on('load', function() {
            $("body").click(function () {
                if ($("#modal_error").is(":visible")) {
                    $("#modal_error").hide();
                }
            });
        });

        function renderTeamTags() {
            // Remove all existing tags
            $teamContainer.find('.tag').remove();

            // Add each tag before the input field
            surveyTeamMembers.forEach((member, index) => {
                const $tag = $('<div class="tag"></div>');
                $tag.append(`<span>${escapeHtml(member)}</span>`);
                const $removeBtn = $('<button class="tag-remove" type="button">&times;</button>');
                $removeBtn.on('click', function() {
                    surveyTeamMembers.splice(index, 1);
                    renderTeamTags();
                    validateFormFields();
                });
                $tag.append($removeBtn);
                $teamInput.before($tag);
            });
        }

        function addTeamMember(name) {
            const trimmedName = name.trim();
            if (trimmedName && !surveyTeamMembers.includes(trimmedName)) {
                surveyTeamMembers.push(trimmedName);
                renderTeamTags();
                validateFormFields();
            }
            $teamInput.val('');
        }

        // Handle Enter key and comma in team input
        $teamInput.on('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                addTeamMember($teamInput.val());
            }
        });

        // Handle blur to add incomplete entry
        $teamInput.on('blur', function() {
            const value = $teamInput.val().trim();
            if (value) {
                addTeamMember(value);
            }
        });

        // Click on container focuses the input
        $teamContainer.on('click', function(e) {
            if (e.target === $teamContainer[0]) {
                $teamInput.focus();
            }
        });

        // Location Search with Nominatim API
        let locationSearchTimeout = null;
        let selectedLocation = null;

        $('#locationSearch').on('input', function() {
            const query = $(this).val().trim();

            // Clear previous timeout
            if (locationSearchTimeout) {
                clearTimeout(locationSearchTimeout);
            }

            // Clear results if query is too short
            if (query.length < 3) {
                $('#locationResults').removeClass('show').empty();
                $('#locationSpinner').removeClass('active');
                return;
            }

            // Show spinner
            $('#locationSpinner').addClass('active');

            // Debounce search
            locationSearchTimeout = setTimeout(function() {
                searchLocation(query);
            }, 500);
        });

        function searchLocation(query) {
            // OpenStreetMap Nominatim API
            const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=10&addressdetails=1`;

            $.ajax({
                url: url,
                method: 'GET',
                headers: {
                    'User-Agent': 'SpeleoDB Survey Tool'
                },
                success: function(results) {
                    $('#locationSpinner').removeClass('active');
                    displayLocationResults(results);
                },
                error: function() {
                    $('#locationSpinner').removeClass('active');
                    $('#locationResults').removeClass('show').empty();
                }
            });
        }

        function displayLocationResults(results) {
            const $resultsContainer = $('#locationResults');
            $resultsContainer.empty();

            if (results.length === 0) {
                $resultsContainer.removeClass('show');
                return;
            }

            results.forEach(function(result) {
                const $item = $('<div class="location-result-item"></div>');

                const displayName = result.display_name;
                const parts = displayName.split(', ');
                const mainName = parts.slice(0, 2).join(', ');
                const details = parts.slice(2).join(', ');

                $item.append(`<div class="location-name">${escapeHtml(mainName)}</div>`);
                if (details) {
                    $item.append(`<div class="location-details">${escapeHtml(details)}</div>`);
                }

                $item.on('click', function() {
                    selectLocation(result);
                });

                $resultsContainer.append($item);
            });

            $resultsContainer.addClass('show');
        }

        function selectLocation(location) {
            selectedLocation = location;

            // Set the search input to the selected location
            $('#locationSearch').val(location.display_name);

            // Store coordinates
            $('#latitude').val(location.lat);
            $('#longitude').val(location.lon);

            // Display coordinates
            $('#latDisplay').text(parseFloat(location.lat).toFixed(6));
            $('#lonDisplay').text(parseFloat(location.lon).toFixed(6));

            // Remove invalid state since location is now selected
            $('#locationSearch').removeClass('invalid-field');

            // Hide results
            $('#locationResults').removeClass('show').empty();
        }

        // Close location results when clicking outside
        $(document).on('click', function(e) {
            if (!$(e.target).closest('.location-search-wrapper').length) {
                $('#locationResults').removeClass('show');
            }
        });

        // Remove red highlight when user changes input
        $('#caveName, #surveyName, #locationSearch').on('input', function() {
            $(this).removeClass('invalid-field');
        });

        $('#surveyDate').on('change input', function() {
            $(this).removeClass('invalid-date');
        });

        // Individual field validation functions
        function validateCaveName() {
            const caveName = $('#caveName').val().trim();
            if (!caveName) {
                $('#caveName').addClass('invalid-field');
                return false;
            } else {
                $('#caveName').removeClass('invalid-field');
                return true;
            }
        }

        function validateSurveyName() {
            const surveyName = $('#surveyName').val().trim();
            if (!surveyName) {
                $('#surveyName').addClass('invalid-field');
                return false;
            } else {
                $('#surveyName').removeClass('invalid-field');
                return true;
            }
        }

        function validateLocation() {
            const latitude = $('#latitude').val();
            const longitude = $('#longitude').val();
            if (!latitude || !longitude) {
                $('#locationSearch').addClass('invalid-field');
                return false;
            } else {
                $('#locationSearch').removeClass('invalid-field');
                return true;
            }
        }

        function validateSurveyDate() {
            const surveyDate = $('#surveyDate').val();
            if (!validateDate(surveyDate)) {
                $('#surveyDate').addClass('invalid-date');
                return false;
            } else {
                $('#surveyDate').removeClass('invalid-date');
                return true;
            }
        }

        // Validate fields on blur (lose focus)
        $('#caveName').on('blur', function() {
            validateCaveName();
        });

        $('#surveyName').on('blur', function() {
            validateSurveyName();
        });

        $('#locationSearch').on('blur', function() {
            // Only validate if there's text but no coordinates selected
            if ($('#locationSearch').val().trim() && !$('#latitude').val()) {
                validateLocation();
            }
        });

        $('#surveyDate').on('blur', function() {
            validateSurveyDate();
        });

        function validateFormFields() {
            let isValid = true;
            let errors = [];

            // Validate Cave Name
            if (!validateCaveName()) {
                errors.push('Cave Name');
                isValid = false;
            }

            // Validate Survey Name
            if (!validateSurveyName()) {
                errors.push('Survey Name');
                isValid = false;
            }

            // Validate Location
            if (!validateLocation()) {
                errors.push('Location (please select from dropdown)');
                isValid = false;
            }

            // Validate Survey Date
            if (!validateSurveyDate()) {
                errors.push('Survey Date');
                isValid = false;
            }

            return { valid: isValid, errors: errors };
        }

        // Set max date to today (no future dates allowed)
        const today = new Date().toISOString().split('T')[0];
        $('#surveyDate').attr('max', today);

        // Unit switch handler
        let currentUnit = 'feet'; // Default unit is feet
        $('#unitSwitch').on('change', function() {
            if (this.checked) {
                currentUnit = 'feet';
                $('#metersLabel').removeClass('active');
                $('#feetLabel').addClass('active');
            } else {
                currentUnit = 'meters';
                $('#feetLabel').removeClass('active');
                $('#metersLabel').addClass('active');
            }
        });

        // Date validation function
        function validateDate(dateString) {
            if (!dateString) return false;
            const date = new Date(dateString);
            return date instanceof Date && !isNaN(date);
        }

        // Remove red highlight when user changes date
        $('#surveyDate').on('change input', function() {
            $(this).removeClass('invalid-date');
        });

        const surveyTable = attachSurveyTableTool({
            tableBodySelector: '#dataTable tbody',
            dataTableSelector: '#dataTable',
            statusSelector:    '#status',
            addRowBtnSelector: '#addRowBtn',
            clearBtnSelector:  '#clearBtn',
            pasteBtnSelector:  '#pasteExcelBtn',
            COLUMNS: COLUMNS,
            lastRowAllowedColumns: ['station', 'depth'],
            lastRowErrorMessage: function (remove) {
                return 'Error: The last row should only have Station and Depth. Remove: ' + remove.join(', ') + '.';
            },
            validateCell: function (value, column, isLastRow) {
                const v = (value ?? '').trim();
                if (column === 'station') {
                    return v !== '';
                }
                if (column === 'depth') {
                    if (v === '') return false;
                    const n = Number(v);
                    return !isNaN(n) && isFinite(n) && n >= 0;
                }
                if (column === 'length') {
                    if (isLastRow) return v === '';
                    if (v === '') return false;
                    const n = Number(v);
                    return !isNaN(n) && isFinite(n) && n >= 0;
                }
                if (column === 'azimuth') {
                    if (isLastRow) return v === '';
                    if (v === '') return false;
                    const n = Number(v);
                    return !isNaN(n) && isFinite(n) && n >= 0 && n < 360;
                }
                if (['left', 'right', 'up', 'down'].includes(column)) {
                    if (isLastRow) return v === '';
                    if (v === '') return true;
                    const n = Number(v);
                    return !isNaN(n) && isFinite(n) && n >= 0;
                }
                if (['flags', 'comment'].includes(column)) {
                    if (isLastRow) return v === '';
                    return true;
                }
                return true;
            },
            parseClipboardText: function (text) {
                if (!text) return [];
                const lines = text.replace(/\r/g, '\n').split(/\n/).filter(l => l.trim());
                const rows = lines.map(line => {
                    let parts = line.split('\t');
                    if (parts.length === 1) parts = line.split(',');
                    return parts.map(p => p.replace(/^\uFEFF/, '').trim());
                });
                if (rows.length > 0 && /station/i.test(rows[0][0])) rows.shift();
                return rows;
            },
        });

        const renderRows = surveyTable.renderRows;
        const validateTable = surveyTable.validateTable;

        $('#downloadBtn').on('click', function() {
            // Validate form fields first
            const formValidation = validateFormFields();
            if (!formValidation.valid) {
                const errorMessage = 'Missing or invalid fields: ' + formValidation.errors.join(', ');
                $('#status').text(errorMessage)
                            .css({ 'color': 'red', 'font-weight': 'bold' });
                return;
            }

            // Validate the table before proceeding
            if (!validateTable()) {
                $('#status').text('Some cells are invalid. Please correct them before downloading.')
                            .css({ 'color': 'red', 'font-weight': 'bold' });
                return;
            }

            const surveyDate = $('#surveyDate').val();

            // Collect form field data
            const caveName = $('#caveName').val().trim();
            const surveyName = $('#surveyName').val().trim();
            const surveyComment = $('#surveyComment').val().trim();
            const latitude = $('#latitude').val();
            const longitude = $('#longitude').val();

            // Collect table data
            const rows = [];
            $('#dataTable tbody tr').each(function() {
                const row = {};
                $(this).find('td[data-col]').each(function() {
                    const col = $(this).data('col');
                    row[col] = $(this).text().trim();
                });
                if (Object.keys(row).length > 0) {
                    rows.push(row);
                }
            });

            var csrftoken = $('input[name^=csrfmiddlewaretoken]').val();

            // Show spinner
            $("#loading_spinner").show();

            // Build AJAX data object
            const ajaxData = {
                shots: rows,
                survey_date: surveyDate,
                unit: currentUnit,
                cave_name: caveName,
                survey_name: surveyName,
                survey_team: surveyTeamMembers,
                comment: surveyComment
            };

            // Add location coordinates if available
            if (latitude && longitude) {
                ajaxData.latitude = parseFloat(latitude);
                ajaxData.longitude = parseFloat(longitude);
            }

            // AJAX call with all survey data
            $.ajax({
                url: context.endpoint,
                method: "POST",
                data: JSON.stringify(ajaxData),
                contentType: "application/json; charset=utf-8",
                cache: false,
                beforeSend: function (xhr) {
                    xhr.setRequestHeader("X-CSRFToken", csrftoken);
                    return true;
                },
                success: function(response) {
                    // Hide spinner
                    $("#loading_spinner").hide();
                    $('#downloadBtn').prop('disabled', false);

                    // Store the response for later use
                    window.surveyData = response;

                    // Display the content in the modal
                    displayCodeInModal(response);

                    $('#status').text('Survey generated successfully!')
                                .css({ 'color': 'green', 'font-weight': 'bold' });
                },
                error: function(xhr, status, error) {
                    // Hide spinner and show error
                    $("#loading_spinner").hide();
                    $('#downloadBtn').prop('disabled', false);

                    // Try to extract error message from response
                    let errorMessage = error;
                    if (xhr.responseJSON && xhr.responseJSON.error) {
                        errorMessage = xhr.responseJSON.error;
                    } else if (xhr.responseJSON && xhr.responseJSON.detail) {
                        errorMessage = xhr.responseJSON.detail;
                    } else if (xhr.responseText) {
                        try {
                            const response = JSON.parse(xhr.responseText);
                            errorMessage = response.error || response.detail || response.message || error;
                        } catch (e) {
                            errorMessage = xhr.responseText.substring(0, 200); // Limit length
                        }
                    }

                    // Display error in modal
                    $("#modal_error_txt").text(errorMessage);
                    $("#modal_error").css('display', 'flex');

                    $('#status').text('Error occurred. See details.')
                                .css({ 'color': 'red', 'font-weight': 'bold' });
                }
            });

        });

        // Store original code for copying
        let originalCode = '';

        // Function to display code in modal with line numbers
        function displayCodeInModal(code) {
            // Store original code for copy/download
            originalCode = code;

            // Escape HTML and create code block
            const escapedCode = $('<div>').text(code).html();
            $('#codeDisplay').html('<pre class="line-numbers"><code class="language-makefile">' + escapedCode + '</code></pre>');

            // Highlight with Prism
            window.Prism.highlightElement($('#codeDisplay code')[0]);

            // After highlighting, wrap form feed characters in span for visual styling
            const $codeElement = $('#codeDisplay code');
            $codeElement.html($codeElement.html().replace(/\f/g, '<span class="ff-char">\f</span>'));

            // Show modal
            $('#resultModal').addClass('show');
        }

        // Close modal handlers
        $('#closeModal').on('click', function() {
            $('#resultModal').removeClass('show');
        });

        // Track mousedown position to distinguish clicks from drag selections
        let mouseDownTarget = null;
        $('#resultModal').on('mousedown', function(e) {
            mouseDownTarget = e.target;
        });

        $('#resultModal').on('click', function(e) {
            // Only close if mousedown and click happened on the same overlay element
            if (e.target === this && mouseDownTarget === this) {
                $('#resultModal').removeClass('show');
            }
            mouseDownTarget = null;
        });

        // ESC key to close modal
        $(document).on('keydown', function(e) {
            if (e.key === 'Escape' && $('#resultModal').hasClass('show')) {
                $('#resultModal').removeClass('show');
            }
        });

        // Copy to clipboard
        let copyButtonTimeout = null;
        const originalCopyButtonHTML = '<svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"/><path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"/></svg> Copy to Clipboard';
        const copiedButtonHTML = '<svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z"/></svg> Copied!';

        $('#copyCodeBtn').on('click', function() {
            const $btn = $('#copyCodeBtn');

            // Clear any existing timeout
            if (copyButtonTimeout) {
                clearTimeout(copyButtonTimeout);
            }

            navigator.clipboard.writeText(originalCode).then(function() {
                $btn.html(copiedButtonHTML);
                copyButtonTimeout = setTimeout(function() {
                    $btn.html(originalCopyButtonHTML);
                    copyButtonTimeout = null;
                }, 2000);
            }).catch(function(err) {
                alert('Failed to copy to clipboard');
            });
        });

        // Download file
        $('#downloadCodeBtn').on('click', function() {
            const blob = new Blob([originalCode], { type: 'text/plain' });
            const a = document.createElement('a');
            document.body.appendChild(a);
            a.href = window.URL.createObjectURL(blob);
            a.style.display = 'none';
            a.download = 'survey.dat';
            a.click();
            window.URL.revokeObjectURL(a.href);
            a.remove();
        });

        renderRows([]);
}
