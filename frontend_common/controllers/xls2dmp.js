import { attachSurveyTableTool } from '../../frontend_private/static/private/js/forms/survey_table_tool.js';

export function init(context) {
    const COLUMNS = ['depth', 'length', 'azimuth', 'left', 'right', 'up', 'down'];
        const $tbody = $('#dataTable tbody');
        const $statusEl = $('#status');

        $(window).on('load', function() {
            $("body").click(function () {
                if ($("#modal_error").is(":visible")) {
                    $("#modal_error").hide();
                }
            });
        });
        
        const today = new Date().toISOString().split('T')[0];
        $('#surveyDate').attr('max', today);
        
        let currentUnit = 'feet';
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

        let surveyDirection = 'in';
        $('#directionSwitch').on('change', function() {
            if (this.checked) {
                surveyDirection = 'out';
                $('#inLabel').removeClass('active');
                $('#outLabel').addClass('active');
            } else {
                surveyDirection = 'in';
                $('#outLabel').removeClass('active');
                $('#inLabel').addClass('active');
            }
        });

        function validateDate(dateString) {
            if (!dateString) return false;
            const date = new Date(dateString);
            return date instanceof Date && !isNaN(date);
        }

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
            lastRowAllowedColumns: ['depth'],
            lastRowErrorMessage: function (remove) {
                return 'Error: The last row should only have Station Depth. Remove: ' + remove.join(', ') + '.';
            },
            validateCell: function (value, column, isLastRow) {
                const v = (value ?? '').trim();
                if (column === 'depth') {
                    if (v === '') return false;
                    const n = parseFloat(v);
                    return !isNaN(n) && isFinite(n) && n >= 0;
                }
                if (column === 'length') {
                    if (isLastRow) return v === '';
                    if (v === '') return false;
                    const n = parseFloat(v);
                    return !isNaN(n) && isFinite(n) && n >= 0;
                }
                if (column === 'azimuth') {
                    if (isLastRow) return v === '';
                    if (v === '') return false;
                    const n = parseFloat(v);
                    return !isNaN(n) && isFinite(n) && n >= 0 && n < 360;
                }
                if (['left', 'right', 'up', 'down'].includes(column)) {
                    if (isLastRow) return v === '';
                    if (v === '') return true;
                    const n = parseFloat(v);
                    return !isNaN(n) && isFinite(n) && n >= 0;
                }
                return true;
            },
            parseClipboardText: function (text) {
                // xls2dmp accepts clipboard data that may include an optional
                // leading "Station #" column which we strip so the shot
                // columns line up with COLUMNS.
                if (!text) return [];
                const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n').filter(l => l.trim());
                let rows = lines.map(line => {
                    let parts = line.split('\t');
                    if (parts.length === 1 && line.includes(',')) {
                        parts = [];
                        let current = '';
                        let inQuotes = false;
                        for (let i = 0; i < line.length; i++) {
                            const char = line[i];
                            const nextChar = line[i + 1];
                            if (char === '"') {
                                if (inQuotes && nextChar === '"') {
                                    current += '"'; i++;
                                } else {
                                    inQuotes = !inQuotes;
                                }
                            } else if (char === ',' && !inQuotes) {
                                parts.push(current); current = '';
                            } else {
                                current += char;
                            }
                        }
                        parts.push(current);
                    }
                    return parts.map(p => {
                        let cleaned = p.replace(/^\uFEFF/, '').trim();
                        if (cleaned.startsWith('"') && cleaned.endsWith('"')) {
                            cleaned = cleaned.slice(1, -1);
                        }
                        return cleaned;
                    });
                });
                if (rows.length > 0 && rows[0].length > 0) {
                    const firstCell = rows[0][0].trim();
                    if (/^station/i.test(firstCell)) {
                        const headerRow = rows[0];
                        const stationColIndex = headerRow.findIndex(cell =>
                            /^station\s*#?$/i.test(cell.trim())
                        );
                        rows.shift();
                        if (stationColIndex !== -1) {
                            rows = rows.map(row => {
                                const newRow = [...row];
                                newRow.splice(stationColIndex, 1);
                                return newRow;
                            });
                        }
                    }
                }
                return rows.filter(row => row.some(cell => cell.trim() !== ''));
            },
        });

        // Expose the helpers the rest of the template expects.
        const renderRows = surveyTable.renderRows;
        const validateTable = surveyTable.validateTable;

        $('#downloadBtn').on('click', function() {
            if (!validateTable()) {
                $('#status').text('Some cells are invalid. Please correct them before downloading.')
                            .css({ 'color': 'red', 'font-weight': 'bold' });
                return;
            }

            const surveyDate = $('#surveyDate').val();
            if (!validateDate(surveyDate)) {
                $('#surveyDate').addClass('invalid-date');
                $('#status').text('Please enter a valid survey date.')
                            .css({ 'color': 'red', 'font-weight': 'bold' });
                return;
            } else {
                $('#surveyDate').removeClass('invalid-date');
            }

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

            $("#loading_spinner").show();

            $.ajax({
                url: context.endpoint,
                method: "POST",
                data: JSON.stringify({ 
                    shots: rows,
                    survey_date: surveyDate,
                    unit: currentUnit,
                    direction: surveyDirection
                }),
                contentType: "application/json; charset=utf-8",
                cache: false,
                beforeSend: function (xhr) {
                    xhr.setRequestHeader("X-CSRFToken", csrftoken);
                    return true;
                },
                success: function(response) {
                    const blob = new Blob([response], { type: 'application/octet-stream' });
                    const a = document.createElement('a');
                    document.body.appendChild(a);
                    a.href = window.URL.createObjectURL(blob);
                    a.style.display = 'none';
                    a.download = 'survey.dmp';
                    a.click();
                    window.URL.revokeObjectURL(a.href);
                    a.remove();
                    
                    $("#loading_spinner").hide();
                    $('#downloadBtn').prop('disabled', false);
                    $('#status').text('Download successful!')
                                .css({ 'color': 'green', 'font-weight': 'bold' });
                },
                error: function(xhr, status, error) {
                    $("#loading_spinner").hide();
                    $('#downloadBtn').prop('disabled', false);
                    
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
                            errorMessage = xhr.responseText.substring(0, 200);
                        }
                    }
                    
                    $("#modal_error_txt").text(errorMessage);
                    $("#modal_error").css('display', 'flex');
                    $('#status').text('Error occurred. See details.')
                                .css({ 'color': 'red', 'font-weight': 'bold' });
                }
            });

        });

        renderRows([]);
}
