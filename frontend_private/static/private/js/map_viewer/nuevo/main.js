const UX = {
    // Function to hide loading overlay with smooth transition
    hideLoadingOverlay() {
        const overlay = $('#loading-overlay');
        if (overlay) {
            overlay.addClass('hide');
            // Remove from DOM after transition completes
            setTimeout(() => {
                // overlay.style.display = 'none';
                overlay.remove();
            }, 500);
        }
    },

    // Function to update loading text
    // updateLoadingText(text, subtext = '') {
    //     const textElement = document.querySelector('.loading-text');
    //     const subtextElement = document.querySelector('.loading-subtext');
    //     if (textElement) textElement.textContent = text;
    //     if (subtextElement) subtextElement.textContent = subtext;
    // },
    updateLoadingText(text, subtext = '') {
        const $textElement = $('.loading-text');
        const $subtextElement = $('.loading-subtext');

        if ($textElement.length) $textElement.text(text);
        if ($subtextElement.length) $subtextElement.text(subtext);
    },

    showNotification(type, message, duration = 3000) {
        const notification = document.createElement('div');
        notification.className = 'notification-toast';

        const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
        const colors = { success: '#10b981', error: '#ef4444', info: '#00D8FF', warning: '#f59e0b' };

        notification.innerHTML = `
            <div class="notification-icon">${icons[type] || icons.info}</div>
            <div class="notification-message">${message}</div>
        `;

        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${colors[type] || colors.info};
            color: white;
            padding: 16px 24px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 12px;
            z-index: 10050;
            box-shadow: 0 10px 25px rgba(0,0,0,0.35);
            opacity: 0;
            transform: translateY(-8px);
            transition: opacity .2s ease, transform .2s ease;
        `;

        const iconEl = notification.querySelector('.notification-icon');
        if (iconEl) {
            iconEl.style.cssText = "font-size: 16px;";
        }
        const msgEl = notification.querySelector('.notification-message');
        if (msgEl) {
            msgEl.style.cssText = "line-height: 1.4;"
        }

        document.body.appendChild(notification);
        requestAnimationFrame(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateY(0)';
        });

        const timeout = Math.max(1000, Number(duration) || 3000);
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-8px)';
            setTimeout(() => notification.remove(), 200);
        }, timeout);
    }
};
