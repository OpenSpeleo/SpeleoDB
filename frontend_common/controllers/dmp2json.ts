import { attachCodeResultModal } from '../presentation/code-result.ts';
import type { Dmp2JsonContext } from '../../ts-types/controllers/dmp2json.ts';
import type { SurveyToolAjaxFailure, SurveyToolErrorBody, SurveyShot, SurveyLocation, CompassSurveyPayload } from '../../ts-types/domain/survey-tools.ts';
import { attachToolFileUpload } from '../../frontend_private/static/private/ts/forms/tool_file_upload.ts';

export function init(context: Dmp2JsonContext) {
    const $downloadBtn = $('#downloadBtn');
        const $statusEl = $('#status');

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

        $('#downloadBtn').on('click', function() {
            const selectedFile = dropzone.getFile();
            if (!selectedFile) {
                dropzone.setStatus('Please select a DMP file first.', 'red', 'bold');
                return;
            }

            var csrftoken = $('input[name^=csrfmiddlewaretoken]').val() as string;

            // Show spinner
            $("#loading_spinner").show();
            $downloadBtn.prop('disabled', true);

            // Create FormData and append the file
            const formData = new FormData();
            formData.append('file', selectedFile);

            // AJAX call to convert DMP to JSON
            $.ajax({
                url: context.endpoint,
                method: "POST",
                data: formData,
                processData: false,
                contentType: false,
                cache: false,
                beforeSend: function (xhr) {
                    xhr.setRequestHeader("X-CSRFToken", csrftoken);
                    return true;
                },
                success: function(response: unknown) {
                    // Hide spinner
                    $("#loading_spinner").hide();
                    $downloadBtn.prop('disabled', false);

                    // Response should be JSON string or object
                    let jsonString;
                    if (typeof response === 'string') {
                        jsonString = response;
                    } else {
                        jsonString = JSON.stringify(response, null, 2);
                    }

                    // Store the response for later use
                    window.surveyData = jsonString;

                    // Display the content in the modal
                    displayCodeInModal(jsonString);

                    $statusEl.text('Conversion successful!')
                              .css({ 'color': 'green', 'font-weight': 'bold' });
                },
                error: function(xhr: SurveyToolAjaxFailure, status, error) {
                    // Hide spinner and show error
                    $("#loading_spinner").hide();
                    $downloadBtn.prop('disabled', false);

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

                    $statusEl.text('Error occurred. See details.')
                              .css({ 'color': 'red', 'font-weight': 'bold' });
                }
            });
        });

        const displayCodeInModal = attachCodeResultModal({
            language: 'json', mimeType: 'application/json', fileName: 'survey.json',
        });
}
