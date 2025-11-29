export const Notification = {
    show(type, message, duration = 3000) {
        // Reuse existing toast or create one
        // The legacy code used Alpine or just global HTML.
        // We'll create a simple container if it doesn't exist
        
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.className = 'fixed bottom-4 right-4 z-50 flex flex-col gap-2';
            document.body.appendChild(container);
        }
        
        const el = document.createElement('div');
        const bgColor = type === 'error' ? 'bg-red-500' : (type === 'success' ? 'bg-emerald-500' : 'bg-slate-700');
        
        el.className = `${bgColor} text-white px-4 py-3 rounded shadow-lg transform transition-all duration-300 translate-y-full opacity-0 flex items-center`;
        el.innerHTML = `
            <span class="mr-2">${type === 'error' ? '⚠️' : (type === 'success' ? '✅' : 'ℹ️')}</span>
            <span>${message}</span>
        `;
        
        container.appendChild(el);
        
        // Animate in
        requestAnimationFrame(() => {
            el.classList.remove('translate-y-full', 'opacity-0');
        });
        
        setTimeout(() => {
            el.classList.add('opacity-0', 'translate-y-2');
            setTimeout(() => el.remove(), 300);
        }, duration);
    }
};





