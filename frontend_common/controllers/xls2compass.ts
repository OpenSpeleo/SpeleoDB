import { attachCodeResultModal } from '../presentation/code-result.ts';
import { validateCell, parseClipboardText } from '../survey/xls2compass.ts';
import type { Xls2CompassContext } from '../../ts-types/controllers/xls2compass.ts';
import type { SurveyToolAjaxFailure, SurveyToolErrorBody, SurveyShot, SurveyLocation, CompassSurveyPayload } from '../../ts-types/domain/survey-tools.ts';
import { attachSurveyTableTool } from '../../frontend_private/static/private/ts/forms/survey_table_tool.ts';
import { escapeHtml } from '../../frontend_private/static/private/ts/xss-helpers.ts';

export function init(context: Xls2CompassContext) {
    const COLUMNS = ["station", "depth", "length", "azimuth", "left", "right", "up", "down", "flags", "comment"];
        const $tbody = $('#dataTable tbody');
        const $statusEl = $('#status');

        // Survey Team Tags
        const surveyTeamMembers: string[] = [];
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

        function addTeamMember(name: string) {
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
                addTeamMember($teamInput.val() as string);
            }
        });

        // Handle blur to add incomplete entry
        $teamInput.on('blur', function() {
            const value = ($teamInput.val() as string).trim();
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
        let locationSearchTimeout: ReturnType<typeof setTimeout> | null = null;
        let selectedLocation: SurveyLocation | null = null;

        $('#locationSearch').on('input', function() {
            const query = ($(this).val() as string).trim();

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

        function searchLocation(query: string) {
            // OpenStreetMap Nominatim API
            const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=10&addressdetails=1`;

            $.ajax({
                url: url,
                method: 'GET',
                headers: {
                    'User-Agent': 'SpeleoDB Survey Tool'
                },
                success: function(results: unknown) {
                    $('#locationSpinner').removeClass('active');
                    displayLocationResults(results as SurveyLocation[]);
                },
                error: function() {
                    $('#locationSpinner').removeClass('active');
                    $('#locationResults').removeClass('show').empty();
                }
            });
        }

        function displayLocationResults(results: SurveyLocation[]) {
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

        function selectLocation(location: SurveyLocation) {
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
            const caveName = ($('#caveName').val() as string).trim();
            if (!caveName) {
                $('#caveName').addClass('invalid-field');
                return false;
            } else {
                $('#caveName').removeClass('invalid-field');
                return true;
            }
        }

        function validateSurveyName() {
            const surveyName = ($('#surveyName').val() as string).trim();
            if (!surveyName) {
                $('#surveyName').addClass('invalid-field');
                return false;
            } else {
                $('#surveyName').removeClass('invalid-field');
                return true;
            }
        }

        function validateLocation() {
            const latitude = $('#latitude').val() as string;
            const longitude = $('#longitude').val() as string;
            if (!latitude || !longitude) {
                $('#locationSearch').addClass('invalid-field');
                return false;
            } else {
                $('#locationSearch').removeClass('invalid-field');
                return true;
            }
        }

        function validateSurveyDate() {
            const surveyDate = $('#surveyDate').val() as string;
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
            if (($('#locationSearch').val() as string).trim() && !$('#latitude').val()) {
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
        const today = new Date().toISOString().split('T')[0]!;
        $('#surveyDate').attr('max', today);

        // Unit switch handler
        let currentUnit = 'feet'; // Default unit is feet
        $('#unitSwitch').on('change', function() {
            if ((this as HTMLInputElement).checked) {
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
        function validateDate(dateString: string) {
            if (!dateString) return false;
            const date = new Date(dateString);
            return date instanceof Date && !isNaN(date as unknown as number);
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
            validateCell,
            parseClipboardText,
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

            const surveyDate = $('#surveyDate').val() as string;

            // Collect form field data
            const caveName = ($('#caveName').val() as string).trim();
            const surveyName = ($('#surveyName').val() as string).trim();
            const surveyComment = ($('#surveyComment').val() as string).trim();
            const latitude = $('#latitude').val() as string;
            const longitude = $('#longitude').val() as string;

            // Collect table data
            const rows: SurveyShot[] = [];
            $('#dataTable tbody tr').each(function() {
                const row: SurveyShot = {};
                $(this).find('td[data-col]').each(function() {
                    const col = $(this).data('col') as string;
                    row[col] = $(this).text().trim();
                });
                if (Object.keys(row).length > 0) {
                    rows.push(row);
                }
            });

            var csrftoken = $('input[name^=csrfmiddlewaretoken]').val() as string;

            // Show spinner
            $("#loading_spinner").show();

            // Build AJAX data object
            const ajaxData: CompassSurveyPayload = {
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
                success: function(response: unknown) {
                    // Hide spinner
                    $("#loading_spinner").hide();
                    $('#downloadBtn').prop('disabled', false);

                    // Store the response for later use
                    window.surveyData = response as string;

                    // Display the content in the modal
                    displayCodeInModal(response as string);

                    $('#status').text('Survey generated successfully!')
                                .css({ 'color': 'green', 'font-weight': 'bold' });
                },
                error: function(xhr: SurveyToolAjaxFailure, status, error) {
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
                            const response = JSON.parse(xhr.responseText) as SurveyToolErrorBody;
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

        const displayCodeInModal = attachCodeResultModal({
            language: 'makefile', mimeType: 'text/plain', fileName: 'survey.dat',
            afterHighlight() {
                // After highlighting, wrap form feed characters in span for visual styling
                const $codeElement = $('#codeDisplay code');
                $codeElement.html($codeElement.html().replace(/\f/g, '<span class="ff-char">\f</span>'));
            },
        });

        renderRows([]);
}
