import { GPXImport } from './gpx_import.js';

describe('GPX import modal dismissal', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <div id="import-gpx-modal">
                <input id="gpx-file-input" type="file">
                <div id="gpx-drop-zone"></div>
                <div id="gpx-selected-file" class="hidden"></div>
                <div id="gpx-error-message" class="hidden"></div>
                <button id="gpx-upload-btn"></button>
                <span id="gpx-upload-text"></span>
                <span id="gpx-upload-spinner"></span>
            </div>
            <div id="gpx-warning-modal" class="hidden"></div>`;
        GPXImport.init('csrf-token');
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('does not dismiss when the backdrop is clicked', () => {
        const modal = document.getElementById('import-gpx-modal');

        modal.click();

        expect(modal.classList.contains('hidden')).toBe(false);
    });
});
