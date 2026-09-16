import fs from 'node:fs';
import path from 'node:path';

function fragment(file) {
    const template = document.createElement('template');
    template.innerHTML = fs.readFileSync(path.join(process.cwd(), file), 'utf8')
        .replace(/{%[\s\S]*?%}/g, '')
        .replace(/{{[\s\S]*?}}/g, '');
    return template.content;
}

describe('template layout contracts after inline style removal', () => {
    it('keeps both chart containers positioned and fixed-height for responsive Chart.js sizing', () => {
        const page = fragment('frontend_private/templates/pages/dashboard.html');
        for (const id of ['commits-chart', 'projects-chart']) {
            const wrapper = page.getElementById(id).parentElement;
            expect(wrapper.classList.contains('relative')).toBe(true);
            expect(wrapper.classList.contains('h-[280px]')).toBe(true);
        }
    });

    it.each(['xls2compass', 'xls2dmp'])('keeps %s large pasted tables inside a bounded scroll area', tool => {
        const page = fragment(`frontend_private/templates/pages/tools/${tool}.html`);
        const wrapper = page.getElementById('dataTable').parentElement;
        expect(wrapper.classList.contains('overflow-auto')).toBe(true);
        expect(wrapper.classList.contains('max-h-[520px]')).toBe(true);
        expect(wrapper.classList.contains('border')).toBe(true);
        expect(wrapper.classList.contains('border-[#eef6ff]')).toBe(true);
        expect(wrapper.classList.contains('rounded-[8px]')).toBe(true);
    });

    it('keeps the required Compass fields visually identified', () => {
        const page = fragment('frontend_private/templates/pages/tools/xls2compass.html');
        const markers = [...page.querySelectorAll('.form-group label span')]
            .filter(marker => marker.textContent === '*');
        expect(markers).toHaveLength(5);
        expect(markers.every(marker => marker.classList.contains('text-[#ff8900]'))).toBe(true);
    });

    it('keeps the feedback midpoint label offset', () => {
        const page = fragment('frontend_private/templates/pages/user/feedback.html');
        const label = [...page.querySelectorAll('div')]
            .find(element => element.textContent === 'Not sure');
        expect(label.classList.contains('ml-[2.65rem]')).toBe(true);
    });

    it.each([
        'frontend_private/templates/pages/map_viewer.html',
        'frontend_public/templates/pages/gis_view_map.html',
    ])('keeps %s on shared canvas sizing without blocking runtime inline height', file => {
        const map = fragment(file).getElementById('map');
        expect(map.classList.contains('map-canvas')).toBe(true);
        expect(map.classList.contains('h-full!')).toBe(false);
    });
});
