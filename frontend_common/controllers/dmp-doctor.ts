import { v2ToolsDmpDoctorCreate } from '@speleodb/api';
import { apiData, webApiOptions } from '../api/client.ts';

import { attachToolFileUpload } from '../../frontend_private/static/private/ts/forms/tool_file_upload.ts';

export function init() {
    const $downloadBtn = $('#downloadBtn');
        const $statusEl = $('#status');

        let currentTab = 'uncorrupt';

        // Set up date inputs - max date is today
        const today = new Date().toISOString().split('T')[0]!;
        $('#surveyDate').attr('max', today);
        $('#surveyDateUncorrupt').attr('max', today);

        // Start value should be Yes
        $('#fixDmpSwitch').prop('checked', true);

        // Tab switching with form reset
        $('.tab-button').on('click', function() {
            const targetTab = $(this).data('tab') as string;

            // Don't reset if clicking same tab
            if (targetTab === currentTab) return;

            // Switch active tab button
            $('.tab-button').removeClass('active');
            $(this).addClass('active');

            // Switch active tab content
            $('.tab-content').removeClass('active');
            $(`#tab-${targetTab}`).addClass('active');

            // Reset form fields (except file)
            resetFormFields();

            currentTab = targetTab;
            $statusEl.text('Tab changed - form reset').css({ 'color': '#94a3b8', 'font-weight': 'normal' });
        });

        function resetFormFields() {
            // Reset all form fields to defaults
            $('#surveyDate').val('');
            $('#surveyDateUncorrupt').val('');
            $('#lengthScaling').val('100').removeClass('invalid');
            $('#compassOffset').val('0').prop('disabled', false).removeClass('invalid');
            $('#depthOffset').val('0').removeClass('invalid');

            // Reset toggles
            $('#fixDmpSwitch').prop('checked', false);
            $('#fixDmpNoLabel').addClass('active');
            $('#fixDmpYesLabel').removeClass('active');

            $('#depthUnitSwitch').prop('checked', true);
            depthOffsetUnit = 'feet';
            $('#metersLabel').removeClass('active');
            $('#feetLabel').addClass('active');
            $('#depthUnitSuffix').text('ft');

            $('#reverseDirectionSwitch').prop('checked', false);
            $('#reverseOffLabel').addClass('active');
            $('#reverseOnLabel').removeClass('active');
        }

        // Fix DMP toggle
        $('#fixDmpSwitch').on('change', function() {
            if ((this as HTMLInputElement).checked) {
                $('#fixDmpNoLabel').removeClass('active');
                $('#fixDmpYesLabel').addClass('active');
            } else {
                $('#fixDmpYesLabel').removeClass('active');
                $('#fixDmpNoLabel').addClass('active');
            }
        });

        // Depth offset unit toggle (Meters/Feet)
        let depthOffsetUnit = 'feet';
        $('#depthUnitSwitch').on('change', function() {
            if ((this as HTMLInputElement).checked) {
                depthOffsetUnit = 'feet';
                $('#metersLabel').removeClass('active');
                $('#feetLabel').addClass('active');
                $('#depthUnitSuffix').text('ft');
            } else {
                depthOffsetUnit = 'meters';
                $('#feetLabel').removeClass('active');
                $('#metersLabel').addClass('active');
                $('#depthUnitSuffix').text('m');
            }
        });

        // Reverse azimuth toggle - sets compass offset to 180 and disables field
        $('#reverseDirectionSwitch').on('change', function() {
            const $compassOffset = $('#compassOffset');

            if ((this as HTMLInputElement).checked) {
                // Store current value if not already 180
                if ($compassOffset.val() !== '180') {
                    $compassOffset.data('previous-value', $compassOffset.val() as string);
                }
                $compassOffset.val('180').prop('disabled', true);
                $('#reverseOffLabel').removeClass('active');
                $('#reverseOnLabel').addClass('active');
            } else {
                // Restore previous value or set to 0
                const previousValue = $compassOffset.data('previous-value') as string || '0';
                $compassOffset.val(previousValue).prop('disabled', false);
                $('#reverseOnLabel').removeClass('active');
                $('#reverseOffLabel').addClass('active');
            }
        });

        // Input validation
        $('#lengthScaling').on('input', function() {
            const val = parseFloat($(this).val() as string);
            if (isNaN(val) || val < 1) {
                $(this).addClass('invalid');
            } else {
                $(this).removeClass('invalid');
            }
        });

        $('#compassOffset').on('input', function() {
            const val = parseFloat($(this).val() as string);
            if (isNaN(val) || val < -360 || val >= 360) {
                $(this).addClass('invalid');
            } else {
                $(this).removeClass('invalid');
            }
        });

        $('#depthOffset').on('input', function() {
            const val = parseFloat($(this).val() as string);
            if (isNaN(val) || val < -1000 || val > 1000) {
                $(this).addClass('invalid');
            } else {
                $(this).removeClass('invalid');
            }
        });

        $(window).on('load', function() {
            $("body").click(function () {
                if ($("#modal_error").is(":visible")) {
                    $("#modal_error").hide();
                }
            });
        });

        const dropzone = attachToolFileUpload({
            dropZoneSelector:   '#fileDropZone',
            fileInputSelector:  '#fileInput',
            fileNameSelector:   '#fileNameDisplay',
            fileErrorSelector:  '#fileErrorDisplay',
            statusSelector:     '#status',
            actionButtonSelector: '#downloadBtn',
            allowedExtensions: ['dmp'],
            readyMessage: 'File ready for conversion',
            invalidMessage: 'Invalid file type. Please upload a .dmp file',
        });

        // Reset form button
        $('#resetFormBtn').on('click', function() {
            resetFormFields();
            dropzone.reset();
            dropzone.setStatus('Form reset', '#94a3b8', 'normal');
        });

        $('#downloadBtn').on('click', function() {
            const selectedFile = dropzone.getFile();
            if (!selectedFile) {
                dropzone.setStatus('Please select a DMP file first.', 'red', 'bold');
                return;
            }

            // Validate inputs
            const lengthScalingPercent = parseFloat($('#lengthScaling').val() as string);
            if (isNaN(lengthScalingPercent) || lengthScalingPercent < 1) {
                $statusEl.text('Shot Length Scaling must be at least 1%.')
                          .css({ 'color': 'red', 'font-weight': 'bold' });
                $('#lengthScaling').addClass('invalid');
                return;
            }

            // Convert percentage to float (100% = 1.0)
            const lengthScaling = lengthScalingPercent / 100;

            const compassOffset = parseFloat($('#compassOffset').val() as string);
            if (isNaN(compassOffset) || compassOffset < -360 || compassOffset >= 360) {
                $statusEl.text('Compass Offset must be between -360 and 359.')
                          .css({ 'color': 'red', 'font-weight': 'bold' });
                $('#compassOffset').addClass('invalid');
                return;
            }

            const depthOffset = parseFloat($('#depthOffset').val() as string);
            if (isNaN(depthOffset) || depthOffset < -1000 || depthOffset > 1000) {
                $statusEl.text('Depth Offset must be between -1000 and 1000.')
                          .css({ 'color': 'red', 'font-weight': 'bold' });
                $('#depthOffset').addClass('invalid');
                return;
            }


            // Show spinner
            $("#loading_spinner").show();
            $downloadBtn.prop('disabled', true);


            // Add all parameters as JSON
            const fixDmp = $('#fixDmpSwitch').is(':checked');
            // Check both date fields (only one will have a value due to tab resets)
            const surveyDate = $('#surveyDateUncorrupt').val() || $('#surveyDate').val() || null;
            const reverseDirection = $('#reverseDirectionSwitch').is(':checked');

            const adjustments = JSON.stringify({
                fix_dmp: fixDmp,
                survey_date: surveyDate,
                length_scaling: lengthScaling,
                compass_offset: compassOffset,
                reverse_direction: reverseDirection,
                depth_offset: depthOffset,
                depth_offset_unit: depthOffsetUnit,
            });

            // Process DMP file
            apiData(v2ToolsDmpDoctorCreate({ file: selectedFile, data: adjustments }, webApiOptions())).then(response => {
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
                    $downloadBtn.prop('disabled', false);
                    $statusEl.text('Download successful!')
                              .css({ 'color': 'green', 'font-weight': 'bold' });
                            }).catch((error: unknown) => {
                    $("#loading_spinner").hide();
                    $downloadBtn.prop('disabled', false);

                    const errorMessage = error instanceof Error ? error.message : 'Conversion failed.';

                    $("#modal_error_txt").text(errorMessage);
                    $("#modal_error").css('display', 'flex');
                    $statusEl.text('Error occurred. See details.')
                              .css({ 'color': 'red', 'font-weight': 'bold' });
            });
        });
}
