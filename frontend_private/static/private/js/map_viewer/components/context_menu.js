export const ContextMenu = {
    menuEl: null,
    iconDataUrlCache: new Map(),
    iconFetchPromises: new Map(),
    
    init() {
        this.menuEl = document.getElementById('context-menu');
        this.prefetchKnownIcons();
        // Close on click anywhere
        document.addEventListener('click', () => this.hide());
        // Close on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.hide();
        });
    },

    getImageSourcesFromMarkup(markup) {
        if (typeof markup !== 'string' || !markup.includes('src=')) return [];
        const urls = [];
        const srcRegex = /src=(["'])([^"']+)\1/g;
        let match;
        while ((match = srcRegex.exec(markup)) !== null) {
            if (match[2]) {
                urls.push(match[2]);
            }
        }
        return urls;
    },

    async cacheIconAsDataUrl(iconUrl) {
        if (!iconUrl) return null;
        if (this.iconDataUrlCache.has(iconUrl)) {
            return this.iconDataUrlCache.get(iconUrl);
        }
        if (this.iconFetchPromises.has(iconUrl)) {
            return this.iconFetchPromises.get(iconUrl);
        }

        const fetchPromise = fetch(iconUrl, { credentials: 'same-origin' })
            .then((response) => {
                if (!response.ok) throw new Error(`Icon fetch failed: ${response.status}`);
                return response.blob();
            })
            .then((blob) => new Promise((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result);
                reader.readAsDataURL(blob);
            }))
            .then((dataUrl) => {
                if (typeof dataUrl === 'string') {
                    this.iconDataUrlCache.set(iconUrl, dataUrl);
                    return dataUrl;
                }
                return null;
            })
            .catch(() => null)
            .finally(() => {
                this.iconFetchPromises.delete(iconUrl);
            });

        this.iconFetchPromises.set(iconUrl, fetchPromise);
        return fetchPromise;
    },

    prefetchKnownIcons() {
        const knownIcons = Object.values(window.MAPVIEWER_CONTEXT?.icons || {});
        knownIcons.forEach((iconUrl) => {
            this.cacheIconAsDataUrl(iconUrl);
        });
    },

    prefetchIconsFromItems(items) {
        items.forEach((item) => {
            if (!item || item === '-' || typeof item.icon !== 'string') return;
            this.getImageSourcesFromMarkup(item.icon).forEach((iconUrl) => {
                this.cacheIconAsDataUrl(iconUrl);
            });
        });
    },

    getCachedIconMarkup(markup) {
        if (typeof markup !== 'string' || !markup.includes('src=')) {
            return markup || '';
        }
        return markup.replace(/src=(["'])([^"']+)\1/g, (fullMatch, quote, url) => {
            const cachedDataUrl = this.iconDataUrlCache.get(url);
            if (!cachedDataUrl) return fullMatch;
            return `src=${quote}${cachedDataUrl}${quote}`;
        });
    },

    getClampedPosition(clickX, clickY, menuRect, viewportPadding = 8) {
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        let left = clickX;
        let top = clickY;

        // Prefer flipping near edges, then clamp to viewport bounds.
        if (left + menuRect.width > viewportWidth - viewportPadding) {
            left = clickX - menuRect.width;
        }
        if (top + menuRect.height > viewportHeight - viewportPadding) {
            top = clickY - menuRect.height;
        }

        const maxLeft = Math.max(viewportPadding, viewportWidth - menuRect.width - viewportPadding);
        const maxTop = Math.max(viewportPadding, viewportHeight - menuRect.height - viewportPadding);

        left = Math.min(Math.max(left, viewportPadding), maxLeft);
        top = Math.min(Math.max(top, viewportPadding), maxTop);

        return { left, top };
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
        this.prefetchIconsFromItems(items);

        // Build items HTML
        let html = '';
        items.forEach(item => {
            if (item === '-') {
                html += '<div class="context-menu-separator"></div>';
            } else {
                html += `
                    <div class="context-menu-item ${item.disabled ? 'disabled' : ''}">
                        <div class="context-menu-icon">${this.getCachedIconMarkup(item.icon || '')}</div>
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
        
        // Adjust position once dimensions are measurable.
        requestAnimationFrame(() => {
            if (!this.menuEl || this.menuEl.style.display === 'none') return;

            const menuRect = this.menuEl.getBoundingClientRect();
            const { left, top } = this.getClampedPosition(posX, posY, menuRect);
            this.menuEl.style.left = `${left}px`;
            this.menuEl.style.top = `${top}px`;
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


