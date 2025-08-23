// Enhanced loading overlay for station operations
function showStationLoadingOverlay(title, message) {
    const overlay = document.createElement('div');
    overlay.className = 'custom-loading-overlay';
    overlay.innerHTML = `
            <div class="loading-card">
                <div class="loading-spinner"></div>
                <div class="loading-title">${title}</div>
                <div class="loading-message">${message}</div>
            </div>
        `;

    overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            animation: fadeIn 0.2s ease-out;
        `;

    const card = overlay.querySelector('.loading-card');
    card.style.cssText = `
            background: rgba(51, 65, 85, 0.98);
            padding: 32px;
            border-radius: 16px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(148, 163, 184, 0.3);
            min-width: 280px;
        `;

    const spinner = overlay.querySelector('.loading-spinner');
    spinner.style.cssText = `
            width: 48px;
            height: 48px;
            border: 3px solid rgba(56, 189, 248, 0.2);
            border-left: 3px solid #38bdf8;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        `;

    const titleEl = overlay.querySelector('.loading-title');
    titleEl.style.cssText = `
            color: #f1f5f9;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 8px;
        `;

    const messageEl = overlay.querySelector('.loading-message');
    messageEl.style.cssText = `
            color: #94a3b8;
            font-size: 14px;
        `;

    document.body.appendChild(overlay);

    return overlay;
}


function hideStationLoadingOverlay(overlay) {
    if (overlay) {
        overlay.style.animation = 'fadeOut 0.2s ease-out';
        setTimeout(() => overlay.remove(), 200);
    }
}
