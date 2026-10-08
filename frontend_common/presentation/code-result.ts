interface CodeResultOptions {
    language: 'json' | 'makefile';
    mimeType: 'application/json' | 'text/plain';
    fileName: 'survey.json' | 'survey.dat';
    afterHighlight?: () => void;
}

/** Each initialization owns its original text, drag target, and clipboard timer. */
export function attachCodeResultModal(options: CodeResultOptions) {
    // Store original code for copying
    let originalCode = '';

    // Function to display code in modal with line numbers
    function displayCodeInModal(code: string) {
        // Store original code for copy/download
        originalCode = code;

        // Escape HTML and create code block
        const escapedCode = $('<div>').text(code).html();
        $('#codeDisplay').html('<pre class="line-numbers"><code class="language-' + options.language + '">' + escapedCode + '</code></pre>');

        // Highlight with Prism
        window.Prism.highlightElement($('#codeDisplay code')[0]!);

        options.afterHighlight?.();

        // Show modal
        $('#resultModal').addClass('show');
    }

    // Close modal handlers
    $('#closeModal').on('click', function() {
        $('#resultModal').removeClass('show');
    });

    // Track mousedown position to distinguish clicks from drag selections
    let mouseDownTarget: EventTarget | null = null;
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
    let copyButtonTimeout: ReturnType<typeof setTimeout> | null = null;
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
        const blob = new Blob([originalCode], { type: options.mimeType });
        const a = document.createElement('a');
        document.body.appendChild(a);
        a.href = window.URL.createObjectURL(blob);
        a.style.display = 'none';
        a.download = options.fileName;
        a.click();
        window.URL.revokeObjectURL(a.href);
        a.remove();
    });
    return displayCodeInModal;
}
