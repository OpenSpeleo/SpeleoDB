import { attachToolFileUpload } from '../../frontend_private/static/private/js/forms/tool_file_upload.js';

export function init(context) {
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

            var csrftoken = $('input[name^=csrfmiddlewaretoken]').val();

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
                success: function(response) {
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
                error: function(xhr, status, error) {
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
                            const response = JSON.parse(xhr.responseText);
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

        // Store original code for copying
        let originalCode = '';

        // Function to display code in modal with line numbers
        function displayCodeInModal(code) {
            // Store original code for copy/download
            originalCode = code;
            
            // Escape HTML and create code block
            const escapedCode = $('<div>').text(code).html();
            $('#codeDisplay').html('<pre class="line-numbers"><code class="language-json">' + escapedCode + '</code></pre>');
            
            // Highlight with Prism
            window.Prism.highlightElement($('#codeDisplay code')[0]);
            
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
            const blob = new Blob([originalCode], { type: 'application/json' });
            const a = document.createElement('a');
            document.body.appendChild(a);
            a.href = window.URL.createObjectURL(blob);
            a.style.display = 'none';
            a.download = 'survey.json';
            a.click();
            window.URL.revokeObjectURL(a.href);
            a.remove();
        });
}
