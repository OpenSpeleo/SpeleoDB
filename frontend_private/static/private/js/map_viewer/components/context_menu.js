export const ContextMenu = {
    menuEl: null,
    
    init() {
        this.menuEl = document.getElementById('context-menu');
        // Close on click anywhere
        document.addEventListener('click', () => this.hide());
        // Close on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.hide();
        });
    },

    /**
     * Show context menu at map-relative coordinates
     * @param {number} mapX - X position relative to map container
     * @param {number} mapY - Y position relative to map container
     * @param {Array} items - Menu items array
     */
    show(mapX, mapY, items) {
        if (!this.menuEl) this.init();
        if (!this.menuEl) return;

        // Build items HTML
        let html = '';
        items.forEach(item => {
            if (item === '-') {
                html += '<div class="context-menu-separator"></div>';
            } else {
                html += `
                    <div class="context-menu-item ${item.disabled ? 'disabled' : ''}">
                        <div class="context-menu-icon">${item.icon || ''}</div>
                        <div class="context-menu-text">
                            <div>${item.label}</div>
                            ${item.subtitle ? `<div class="context-menu-subtitle">${item.subtitle}</div>` : ''}
                        </div>
                    </div>
                `;
            }
        });

        this.menuEl.innerHTML = html;
        
        // Convert map-relative coords to viewport coords
        const mapEl = document.getElementById('map');
        let posX = mapX;
        let posY = mapY;
        
        if (mapEl) {
            const rect = mapEl.getBoundingClientRect();
            posX = rect.left + mapX;
            posY = rect.top + mapY;
        }
        
        // Position the menu
        this.menuEl.style.left = `${posX}px`;
        this.menuEl.style.top = `${posY}px`;
        this.menuEl.style.display = 'block';
        
        // Adjust position if menu would go off screen (use requestAnimationFrame for accurate measurement)
        requestAnimationFrame(() => {
            const menuRect = this.menuEl.getBoundingClientRect();
            const windowWidth = window.innerWidth;
            const windowHeight = window.innerHeight;

            // If menu would go off right edge, flip to left of click point
            if (menuRect.right > windowWidth) {
                this.menuEl.style.left = `${posX - menuRect.width}px`;
            }
            // If menu would go off bottom edge, flip to above click point
            if (menuRect.bottom > windowHeight) {
                this.menuEl.style.top = `${posY - menuRect.height}px`;
            }
        });

        // Attach click handlers to items
        let itemIndex = 0;
        this.menuEl.childNodes.forEach((node) => {
            if (node.classList && node.classList.contains('context-menu-item')) {
                // Skip separator items in data array
                while (items[itemIndex] === '-') itemIndex++;
                
                const item = items[itemIndex];
                if (item && !item.disabled && item.onClick) {
                    node.onclick = (e) => {
                        e.stopPropagation();
                        this.hide();
                        item.onClick();
                    };
                }
                itemIndex++;
            } else if (node.classList && node.classList.contains('context-menu-separator')) {
                itemIndex++;
            }
        });
    },

    hide() {
        if (this.menuEl) {
            this.menuEl.style.display = 'none';
        }
    }
};


