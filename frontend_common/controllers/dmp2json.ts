import { v2ToolsDmp2jsonCreate } from '@speleodb/api';
import { apiData, webApiOptions } from '../api/client.ts';
import { attachCodeResultModal } from '../presentation/code-result.ts';

import { attachToolFileUpload } from '../../frontend_private/static/private/ts/forms/tool_file_upload.ts';

export function init() {
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


            // Show spinner
            $("#loading_spinner").show();
            $downloadBtn.prop('disabled', true);


            // Convert DMP to JSON
            apiData(v2ToolsDmp2jsonCreate({ file: selectedFile }, webApiOptions())).then(response => response.text()).then(response => {
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
                            }).catch((error: unknown) => {
                    // Hide spinner and show error
                    $("#loading_spinner").hide();
                    $downloadBtn.prop('disabled', false);

                    // Try to extract error message from response
                    const errorMessage = error instanceof Error ? error.message : 'Conversion failed.';

                    // Display error in modal
                    $("#modal_error_txt").text(errorMessage);
                    $("#modal_error").css('display', 'flex');

                    $statusEl.text('Error occurred. See details.')
                              .css({ 'color': 'red', 'font-weight': 'bold' });
            });
        });

        const displayCodeInModal = attachCodeResultModal({
            language: 'json', mimeType: 'application/json', fileName: 'survey.json',
        });
}
