/**
 * Shared drop-zone + file-validation helper for the DMP tool pages
 * (`tools/dmp2json.html` and `tools/dmp_doctor.html`).
 *
 * Both pages offer the same UX:
 *   - click the drop-zone or drag a file onto it
 *   - reject anything whose extension doesn't match `.dmp` (or whatever
 *     `allowedExtensions` says)
 *   - show the file name / an error message
 *   - toggle the primary action button enabled / disabled
 *   - clear on reset
 *
 * What differs between the two pages is what happens AFTER a valid
 * file has been picked (dmp2json renders JSON into a modal; dmp_doctor
 * downloads a processed DMP). That side lives in each template.
 *
 * Usage:
 *   const dropzone = attachToolFileUpload({
 *       dropZoneSelector: '#fileDropZone',
 *       fileInputSelector: '#fileInput',
 *       fileNameSelector: '#fileNameDisplay',
 *       fileErrorSelector: '#fileErrorDisplay',
 *       statusSelector: '#status',
 *       actionButtonSelector: '#downloadBtn',
 *       allowedExtensions: ['dmp'],
 *       readyMessage: 'File ready for conversion',
 *       invalidMessage: 'Invalid file type. Please upload a .dmp file',
 *       onFileSelected: function (file) { ... },    // optional
 *   });
 *
 *   // Later:
 *   const file = dropzone.getFile();
 *   dropzone.reset();
 *
 * Requires: jQuery.
 */

/* exported attachToolFileUpload */

function attachToolFileUpload(options) {
    var $dropZone = $(options.dropZoneSelector);
    var $fileInput = $(options.fileInputSelector);
    var $fileNameDisplay = $(options.fileNameSelector);
    var $fileErrorDisplay = $(options.fileErrorSelector);
    var $actionBtn = options.actionButtonSelector ? $(options.actionButtonSelector) : $();
    var $status = options.statusSelector ? $(options.statusSelector) : $();

    var allowedExtensions = (options.allowedExtensions || []).map(function (e) {
        return String(e).toLowerCase().replace(/^\./, '');
    });
    var readyMessage = options.readyMessage || 'File ready';
    var invalidMessage = options.invalidMessage || 'Invalid file type.';
    var onFileSelected = options.onFileSelected;

    if (!$dropZone.length) { throw new Error('attachToolFileUpload: drop zone not found'); }
    if (!$fileInput.length) { throw new Error('attachToolFileUpload: file input not found'); }

    var selectedFile = null;

    function setStatus(text, color, weight) {
        if (!$status.length) { return; }
        $status.text(text || '');
        if (color || weight) {
            $status.css({
                color: color || '',
                'font-weight': weight || '',
            });
        }
    }

    function reset() {
        selectedFile = null;
        $dropZone.removeClass('has-file invalid-file drag-over');
        $fileNameDisplay.hide().text('');
        $fileErrorDisplay.hide().text('');
        $actionBtn.prop('disabled', true);
        $fileInput.val('');
        setStatus('');
    }

    function handleFile(file) {
        // Reset status-related UI but keep state assignment below.
        $dropZone.removeClass('has-file invalid-file');
        $fileNameDisplay.hide();
        $fileErrorDisplay.hide();
        selectedFile = null;
        $actionBtn.prop('disabled', true);
        setStatus('');

        var fileName = file.name || '';
        var ext = fileName.split('.').pop().toLowerCase();
        if (allowedExtensions.length > 0 && allowedExtensions.indexOf(ext) === -1) {
            $dropZone.addClass('invalid-file');
            $fileErrorDisplay.text(invalidMessage).show();
            return;
        }

        selectedFile = file;
        $dropZone.addClass('has-file');
        $fileNameDisplay.text(fileName).show();
        $actionBtn.prop('disabled', false);
        setStatus(readyMessage, 'green', 'bold');

        if (typeof onFileSelected === 'function') {
            onFileSelected(file);
        }
    }

    $dropZone.on('click', function () { $fileInput.click(); });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(function (eventName) {
        $dropZone[0].addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    ['dragenter', 'dragover'].forEach(function (eventName) {
        $dropZone[0].addEventListener(eventName, function () {
            $dropZone.addClass('drag-over');
        }, false);
    });
    ['dragleave', 'drop'].forEach(function (eventName) {
        $dropZone[0].addEventListener(eventName, function () {
            $dropZone.removeClass('drag-over');
        }, false);
    });
    $dropZone[0].addEventListener('drop', function (e) {
        var files = e.dataTransfer && e.dataTransfer.files;
        if (files && files.length > 0) { handleFile(files[0]); }
    }, false);

    $fileInput.on('change', function (e) {
        if (e.target.files.length > 0) { handleFile(e.target.files[0]); }
    });

    return {
        getFile: function () { return selectedFile; },
        reset: reset,
        setStatus: setStatus,
    };
}
