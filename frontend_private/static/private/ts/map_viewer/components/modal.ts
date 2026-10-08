import { getMapOverlayHost } from './overlay_host.ts';
import { openMapDialog, closeMapDialog } from './dialog_lifecycle.ts';
import { DEFAULTS } from '../defaults.ts';

export const Modal = {
    base(id: string, title: string, content: string, footer: string | null = null, maxWidth = 'max-w-2xl') {
        return `
            <div id="${id}" class="fixed inset-0 bg-srgb-black-50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
                <div class="bg-slate-800 rounded-xl shadow-2xl border border-slate-600 w-full ${maxWidth} flex flex-col max-h-[90vh]">
                    <div class="flex items-center justify-between p-6 border-b border-slate-600 shrink-0">
                        <h2 class="text-xl font-semibold text-white">${title}</h2>
                        <button data-close-modal="${id}" aria-label="Close dialog" class="text-slate-400 hover:text-white transition-colors">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                        </button>
                    </div>

                    <div class="p-6 overflow-y-auto">
                        ${content}
                    </div>

                    ${footer ? `
                    <div class="flex justify-end flow-x-3 p-6 pt-0 mt-auto shrink-0">
                        ${footer}
                    </div>` : ''}
                </div>
            </div>
        `;
    },

    open(id: string, html: string, onOpen: (() => void) | null = null) {
        this.close(id);
        getMapOverlayHost().insertAdjacentHTML('beforeend', html);
        const element = document.getElementById(id);
        openMapDialog(element, { onClose: () => element!.remove(), dismissOnBackdrop: false });

        // Attach standard close handlers to ALL elements with data-close-modal
        const closeBtns = document.querySelectorAll<HTMLElement>(`[data-close-modal="${id}"]`);
        closeBtns.forEach(btn => {
            btn.onclick = () => this.close(id);
        });

        if (onOpen) setTimeout(() => {
            // Closing or replacing a dialog invalidates its delayed form setup.
            if (element?.isConnected && document.getElementById(id) === element) onOpen();
        }, DEFAULTS.UI.MODAL_SETUP_DELAY_MS);
    },

    close(id: string) {
        const el = document.getElementById(id);
        if (el) {
            closeMapDialog(el);
            el.remove();
        }
    }
};
