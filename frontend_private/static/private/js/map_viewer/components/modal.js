export const Modal = {
    base(id, title, content, footer = null, maxWidth = 'max-w-2xl') {
        return `
            <div id="${id}" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full ${maxWidth} flex flex-col max-h-[90vh]">
                    <div class="flex items-center justify-between p-6 border-b border-slate-600 shrink-0">
                        <h2 class="text-xl font-semibold text-white">${title}</h2>
                        <button data-close-modal="${id}" class="text-slate-400 hover:text-white transition-colors">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                        </button>
                    </div>
                    
                    <div class="p-6 overflow-y-auto">
                        ${content}
                    </div>

                    ${footer ? `
                    <div class="flex justify-end space-x-3 p-6 pt-0 mt-auto shrink-0">
                        ${footer}
                    </div>` : ''}
                </div>
            </div>
        `;
    },

    open(id, html, onOpen = null) {
        this.close(id);
        document.body.insertAdjacentHTML('beforeend', html);
        
        // Attach standard close handlers
        const closeBtn = document.querySelector(`[data-close-modal="${id}"]`);
        if (closeBtn) closeBtn.onclick = () => this.close(id);

        const escHandler = (e) => {
            if (e.key === 'Escape') {
                this.close(id);
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
        
        if (onOpen) setTimeout(onOpen, 50);
    },

    close(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }
};


