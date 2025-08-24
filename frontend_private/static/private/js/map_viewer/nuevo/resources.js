const Resource = {
    hideAddResourceForm() {
        const formContainer = $('#add-resource-form');
        if (formContainer.length) {
            formContainer.addClass('hidden');

            // Reset any file displays
            const fileContainers = formContainer.find('.file-upload-area');
            fileContainers.each(function () {
                this.resetFileDisplay($(this));
            });
        }
    },

    // ====================== FILE MANAGEMENT ====================== //

    updateFileDisplay(fileContainer, file) {
        const textDiv = fileContainer.querySelector('.text-center');
        if (!textDiv) return;

        // Check file size limits
        const maxFileSizeMB = 5; // 5MB maximum
        const maxFileSize = maxFileSizeMB * 1024 * 1024;
        const resourceTypeSelect = document.querySelector('select[name="resource_type"]');
        const resourceType = resourceTypeSelect ? resourceTypeSelect.value : '';

        let errorMessage = '';
        let svg_data = null;

        if (resourceType === 'video') {
            svg_data = `
                <svg xmlns="http://www.w3.org/2000/svg" class="icon" viewBox="0 0 1024 1024">
                    <path fill="#FFB89A" d="M862 384H218c-36 0-66-30-66-66v-30c0-36 30-66 66-66h644c36 0 66 30 66 66v30c0 36-30 66-66 66z"/>
                    <path fill="#cbd5e1" d="M823 129H200c-77 0-141 63-141 141v487c0 77 64 140 141 140h623c77 0 140-63 140-140V270c0-78-63-141-140-141zm80 177H760l105-105 15 12c15 15 23 35 23 57v36zm-673 0 104-117h61L286 306h-56zm247-117h170L532 306H368l109-117zm249 0h66L676 306h-60l113-115-3-2zm-583 24c15-15 35-24 57-24h54L150 306h-31v-36c0-22 9-42 24-57zm737 601a80 80 0 0 1-57 23H200a80 80 0 0 1-81-80V366h784v391c0 21-8 41-23 57z"/>
                    <path fill="#3C9" d="M401 771V431l133 77a30 30 0 0 1-30 52l-43-25v132l114-66-8-5a30 30 0 0 1 30-52l98 57-294 170z"/>
                </svg>
            `;
            errorMessage = 'Video files must be under 5MB';

        } else if (resourceType === 'photo') {
            svg_data = `
                <svg xmlns="http://www.w3.org/2000/svg" class="icon" viewBox="0 0 1024 1024">
                    <path fill="#FFB89A" d="M401 617a168 168 0 1 0 336 0 168 168 0 1 0-336 0Z"/>
                    <path fill="#3C9" d="M523 765a204 204 0 1 1 184-292 30 30 0 1 1-54 26 145 145 0 0 0-130-82 144 144 0 1 0 56 277c15-7 33 0 39 16 7 15 0 32-16 39-25 11-52 16-79 16z"/>
                    <path fill="#3C9" d="m687 660-10-2c-16-6-24-23-18-39 3-10 6-22 7-33a30 30 0 1 1 60 6c-2 16-6 32-11 48-4 12-16 20-28 20zm83-274a31 31 0 1 0 63 0 31 31 0 1 0-63 0Z"/>
                    <path fill="#cbd5e1" d="M821 241h-61v-1l-5 1c-23 0-42-25-42-55l1-11v-6c0-39-32-72-72-72H386c-39 0-72 33-72 72v8l1 9c0 30-23 55-46 55l-2-1v1h-13v-56a30 30 0 1 0-60 0v56c-72 6-129 66-129 140v403c0 77 63 141 140 141h616c77 0 141-64 141-141V381c-1-77-64-140-141-140zm81 543c0 21-9 42-24 57a80 80 0 0 1-57 24H205c-21 0-42-9-57-24a80 80 0 0 1-24-57V381c0-21 9-41 24-57 15-15 36-23 57-23h64c27 0 62-20 62-20a125 125 0 0 0 44-106v-5c-1-7 5-12 11-12h256c6 0 12 5 12 12v2a129 129 0 0 0 24 89c6 9 14 16 22 22 0 0 27 18 60 18h61a80 80 0 0 1 80 80v403z"/>
                </svg>
            `;
            errorMessage = 'Photo files must be under 10MB';

        } else if (resourceType === 'document') {
            svg_data = `
                <svg xmlns="http://www.w3.org/2000/svg" class="icon" viewBox="0 0 1024 1024">
                    <path fill="#3C9" d="M714 762h-98a30 30 0 1 0 0 60h98a30 30 0 1 0 0-60zm-227 0H147a30 30 0 1 0 0 60h340a30 30 0 1 0 0-60z"/>
                    <path fill="#FFB89A" d="m838 130 66 66-58 58-66-66z"/>
                    <path fill="#ecececff" d="M744 956H196c-54 0-98-44-98-98V176c0-54 44-98 98-98h419a30 30 0 1 1 0 60H196c-21 0-38 17-38 38v684c0 20 17 37 38 37h548c20 0 37-17 37-38V465a30 30 0 1 1 60 0v395c0 53-44 97-97 97z"/>
                    <path fill="#cbd5e1" d="m908 122-39-39c-24-24-66-22-92 5L420 445l-73 199 199-73 357-357c12-12 20-28 21-44 2-18-4-36-16-48zM513 519l-65 24 23-65 265-265 41 42-264 264zm348-348-42 42-41-42 41-41c3-3 7-4 8-4l38 38c-1 1-1 4-4 7z"/>
                </svg>
            `;

        } else {
            throw new Error(`Unknown resource type: ${resourceType}`);
        }

        if (file.size > maxFileSize) {
            showNotification(
                'error',
                `
                    ${resourceType.charAt(0).toUpperCase() + resourceType.slice(1)} 
                    file size cannot exceed ${maxFileSizeMB}MB. Your file is 
                    ${(file.size / (1024 * 1024)).toFixed(1)}MB
                `
            );

            // Reset the file input
            const fileInput = textDiv.querySelector('input[type="file"]');
            if (fileInput) {
                fileInput.value = '';
            }

            // Optionally show error in the file container
            fileContainer.classList.add('border-red-500');
            fileContainer.classList.remove('border-slate-600', 'border-green-500');

            // Update the display to show error
            textDiv.innerHTML = `
                <div class="w-12 h-12 mx-auto mb-3">${svg_data}</div>
                <p class="text-red-400 font-medium text-sm mb-1">File Too Large!</p>
                <p class="text-slate-300 text-sm">${file.name}</p>
                <p class="text-red-400 text-xs">${errorMessage}</p>
                <p class="text-slate-400 text-xs mt-2">Current file: ${(file.size / (1024 * 1024)).toFixed(1)}MB</p>
                <input type="file" name="file" class="hidden" accept="image/*,video/*,.pdf,.doc,.docx,.mp4,.mov,.avi,.webm">
            `;

            // Re-attach the file input handler
            const newFileInput = textDiv.querySelector('input[type="file"]');
            if (newFileInput) {
                newFileInput.addEventListener('change', (e) => {
                    if (e.target.files && e.target.files.length > 0) {
                        this.updateFileDisplay(fileContainer, e.target.files[0]);
                    }
                });
            }

            return;
        }

        // Format file size
        const fileSize = file.size < 1024 * 1024
            ? (file.size / 1024).toFixed(1) + ' KB'
            : (file.size / (1024 * 1024)).toFixed(1) + ' MB';

        // Save the file input BEFORE any DOM manipulation
        const fileInput = textDiv.querySelector('input[type="file"]');
        if (!fileInput) {
            console.error('File input not found in updateFileDisplay!');
            return;
        }

        // Remove all children except the file input
        const children = Array.from(textDiv.children);
        children.forEach(child => {
            if (child !== fileInput) {
                child.remove();
            }
        });

        // Create new elements
        const svg_div = document.createElement('div');
        svg_div.className = 'w-12 h-12 mx-auto mb-3';
        svg_div.innerHTML = svg_data;

        const statusP = document.createElement('p');
        statusP.className = 'text-green-400 font-medium text-sm mb-1';
        statusP.textContent = 'File Selected!';

        const nameP = document.createElement('p');
        nameP.className = 'text-slate-300 text-sm';
        nameP.textContent = file.name;

        const sizeP = document.createElement('p');
        sizeP.className = 'text-slate-400 text-xs';
        sizeP.textContent = `${fileSize} • ${file.type || 'Unknown type'}`;

        const changeP = document.createElement('p');
        changeP.className = 'text-sky-400 text-xs mt-2 cursor-pointer hover:text-sky-300';
        changeP.textContent = 'Click to change file';
        changeP.onclick = () => fileContainer.click();

        // Add elements in order (file input stays where it is)
        textDiv.insertBefore(svg_div, fileInput);
        textDiv.insertBefore(statusP, fileInput);
        textDiv.insertBefore(nameP, fileInput);
        textDiv.insertBefore(sizeP, fileInput);
        textDiv.appendChild(changeP); // This goes after the file input

        // Add success border
        fileContainer.classList.add('border-green-500');
        fileContainer.classList.remove('border-slate-600', 'border-red-500');
    },

    resetFileDisplay($fileContainer) {
        const $textDiv = $fileContainer.find('.text-center');
        if ($textDiv.length === 0) return;

        $textDiv.html(`
            <svg class="w-12 h-12 text-slate-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
            </svg>
            <p class="text-slate-300 text-sm mb-2">Click to select file or drag and drop</p>
            <p class="text-slate-400 text-xs">Max file size: 5MB • Images, videos, documents accepted</p>
            <input type="file" name="file" class="hidden" accept="image/*,video/*,.pdf,.doc,.docx,.mp4,.mov,.avi,.webm">
        `);

        $fileContainer
            .removeClass('border-green-500')
            .addClass('border-slate-600');

        const $fileInput = $fileContainer.find('input[type="file"]');
        if ($fileInput.length) {
            $fileInput.val('');
        }
    }
};