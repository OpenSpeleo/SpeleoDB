import { validateCell, parseClipboardText } from '../survey/xls2dmp.ts';
import type { Xls2DmpContext } from '../../ts-types/controllers/xls2dmp.ts';
import type { SurveyToolAjaxFailure, SurveyToolErrorBody, SurveyShot, SurveyLocation, CompassSurveyPayload } from '../../ts-types/domain/survey-tools.ts';
import { attachSurveyTableTool } from '../../frontend_private/static/private/ts/forms/survey_table_tool.ts';

export function init(context: Xls2DmpContext) {
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

        const today = new Date().toISOString().split('T')[0]!;
        $('#surveyDate').attr('max', today);

        let currentUnit = 'feet';
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

        let surveyDirection = 'in';
        $('#directionSwitch').on('change', function() {
            if ((this as HTMLInputElement).checked) {
                surveyDirection = 'out';
                $('#inLabel').removeClass('active');
                $('#outLabel').addClass('active');
            } else {
                surveyDirection = 'in';
                $('#outLabel').removeClass('active');
                $('#inLabel').addClass('active');
            }
        });

        function validateDate(dateString: string) {
            if (!dateString) return false;
            const date = new Date(dateString);
            return date instanceof Date && !isNaN(date as unknown as number);
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
            validateCell,
            parseClipboardText,
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

            const surveyDate = $('#surveyDate').val() as string;
            if (!validateDate(surveyDate)) {
                $('#surveyDate').addClass('invalid-date');
                $('#status').text('Please enter a valid survey date.')
                            .css({ 'color': 'red', 'font-weight': 'bold' });
                return;
            } else {
                $('#surveyDate').removeClass('invalid-date');
            }

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
                success: function(response: unknown) {
                    const blob = new Blob([response as BlobPart], { type: 'application/octet-stream' });
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
                error: function(xhr: SurveyToolAjaxFailure, status, error) {
                    $("#loading_spinner").hide();
                    $('#downloadBtn').prop('disabled', false);

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
