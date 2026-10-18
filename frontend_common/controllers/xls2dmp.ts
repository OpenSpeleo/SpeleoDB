import type { V2ToolsXls2dmpCreateBody } from '@speleodb/api';
import { v2ToolsXls2dmpCreate } from '@speleodb/api';
import { apiData, webApiOptions } from '../api/client.ts';
import { validateCell, parseClipboardText } from '../survey/xls2dmp.ts';
import type { SurveyShot } from '../../ts-types/domain/survey-tools.ts';
import { attachSurveyTableTool } from '../../frontend_private/static/private/ts/forms/survey_table_tool.ts';

export function init() {
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

        let currentUnit: V2ToolsXls2dmpCreateBody['unit'] = 'feet';
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

        let surveyDirection: V2ToolsXls2dmpCreateBody['direction'] = 'in';
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

            const rows: V2ToolsXls2dmpCreateBody['shots'] = [];
            $('#dataTable tbody tr').each(function() {
                const row: SurveyShot = {};
                $(this).find('td[data-col]').each(function() {
                    const col = $(this).data('col') as string;
                    row[col] = $(this).text().trim();
                });
                if (Object.keys(row).length > 0) {
                    rows.push({ ...row, depth: row.depth ?? '' });
                }
            });


            $("#loading_spinner").show();

            apiData(v2ToolsXls2dmpCreate({ shots: rows, survey_date: surveyDate, unit: currentUnit, direction: surveyDirection }, webApiOptions())).then(response => {
                    const blob = response;
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
                            }).catch((error: unknown) => {
                    $("#loading_spinner").hide();
                    $('#downloadBtn').prop('disabled', false);

                    const errorMessage = error instanceof Error ? error.message : 'Conversion failed.';

                    $("#modal_error_txt").text(errorMessage);
                    $("#modal_error").css('display', 'flex');
                    $('#status').text('Error occurred. See details.')
                                .css({ 'color': 'red', 'font-weight': 'bold' });
            });

        });

        renderRows([]);
}
