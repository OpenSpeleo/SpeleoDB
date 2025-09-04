// Shared user autocomplete helper
// Usage: attachUserAutocomplete($("#user"), $("#user_suggestions"), autocompleteUrl)

function attachUserAutocomplete($input, $suggestions, autocompleteUrl) {
    let lastQuery = "";
    let pending = null;
    let activeIndex = -1;
    let currentItems = [];
    let debounceTimer = null;

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function render(items) {
        currentItems = items || [];
        if (!currentItems.length) {
            $suggestions.addClass('hidden').empty();
            activeIndex = -1;
            return;
        }

        const maxToShow = Math.min(3, currentItems.length);
        let html = "";
        for (let i = 0; i < maxToShow; i++) {
            const it = currentItems[i];
            const nameHtml = '<span class="truncate">' + escapeHtml(it.name || '') + '</span>';
            const emailHtml = '<span class="text-slate-400 truncate"> &lt;' + escapeHtml(it.email || '') + '&gt;</span>';
            html += '<div class="px-2 py-1 hover:bg-slate-700 cursor-pointer flex items-center gap-2' + (i === activeIndex ? ' bg-slate-700' : '') + '" data-index="' + i + '" data-email="' + escapeHtml(it.email || '') + '">' +
                    nameHtml + emailHtml +
                    '</div>';
        }
        if (currentItems.length > maxToShow) {
            html += '<div class="px-2 py-1 text-slate-400 text-center select-none">…</div>';
        }
        $suggestions.html(html).removeClass('hidden');
    }

    function selectIndex(newIndex) {
        if (currentItems.length === 0) return;
        const maxToShow = Math.min(3, currentItems.length);
        activeIndex = (newIndex + maxToShow) % maxToShow;
        $suggestions.children('div[data-index]').removeClass('bg-slate-700');
        $suggestions.children('div[data-index="' + activeIndex + '"]').addClass('bg-slate-700');
    }

    function commitSelection() {
        if (activeIndex < 0 || activeIndex >= currentItems.length) return;
        const email = currentItems[activeIndex].email;
        $input.val(email);
        $suggestions.addClass('hidden').empty();
    }

    $input.on('keydown', function(e){
        if ($suggestions.hasClass('hidden')) return;
        if (e.key === 'ArrowDown') { e.preventDefault(); e.stopPropagation(); selectIndex(activeIndex + 1); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); e.stopPropagation(); selectIndex(activeIndex - 1); }
        else if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); if (activeIndex === -1 && currentItems.length > 0) { activeIndex = 0; } commitSelection(); }
        else if (e.key === 'Escape') { $suggestions.addClass('hidden').empty(); }
    });

    $input.on('input', function(){
        const val = $input.val().trim();
        if (val.length < 3) { $suggestions.addClass('hidden').empty(); return; }
        if (val === lastQuery) { return; }
        lastQuery = val;
        activeIndex = -1;

        if (debounceTimer) { clearTimeout(debounceTimer); }
        debounceTimer = setTimeout(function(){
            if (pending) { pending.abort(); }
            pending = $.ajax({
                url: autocompleteUrl,
                method: "GET",
                data: { query: val },
                success: function(resp){ render(resp.data); },
                error: function(){ $suggestions.addClass('hidden').empty(); },
                complete: function(){ pending = null; }
            });
        }, 250);
    });

    $suggestions.on('mouseover', 'div[data-index]', function(){
        const idx = parseInt($(this).data('index'));
        selectIndex(idx);
    });

    $suggestions.on('mousedown', 'div[data-index]', function(e){
        e.preventDefault();
        const idx = parseInt($(this).data('index'));
        activeIndex = idx;
        commitSelection();
    });

    $(document).on('click', function(e){
        if (!$(e.target).closest($suggestions).length && !$(e.target).is($input)) {
            $suggestions.addClass('hidden');
        }
    });
}


