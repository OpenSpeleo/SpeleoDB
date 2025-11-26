export const Lightbox = {
    open(imageUrl, title) {
        const lightbox = document.getElementById('photo-lightbox');
        const img = document.getElementById('lightbox-image');
        
        if (!lightbox || !img) return;
        
        img.src = imageUrl;
        lightbox.style.display = 'flex';
        
        // Setup download button if needed
        // For now just show
    },
    
    close() {
        const lightbox = document.getElementById('photo-lightbox');
        if (lightbox) {
            lightbox.style.display = 'none';
            const img = document.getElementById('lightbox-image');
            if (img) img.src = '';
        }
    }
};


