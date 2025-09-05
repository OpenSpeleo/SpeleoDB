const POI = {
    // Load POI Manager Content
    loadPOIManager() {
        const manager = $('#poi-manager-content');
        if (!manager.length) {
            console.error('❌ poi-manager-content element not found!');
            return;
        }

        // Build the POI manager content
        _preparePOIManagerContent(manager);
    }
};

async function _preparePOIManagerContent(manager) {
    // Gather all POIs
    const pois = Array.from(allPOIs.values());
    const totalPOIs = pois.length;

    // Sort POIs by name
    pois.sort((a, b) => (a.name || '').localeCompare(b.name || ''));

    // Build HTML
    let html = `
                <div class="p-6 overflow-y-auto" style="max-height: calc(100vh - 200px);">
                    <div class="mb-6">
                        <div class="flex justify-between items-center mb-4">
                            <h3 class="text-lg font-medium text-white">All Points of Interest</h3>
                            <span class="text-sm text-slate-400">${totalPOIs} Point${totalPOIs !== 1 ? 's' : ''} of Interest total</span>
                        </div>
                    </div>
            `;

    if (totalPOIs === 0) {
        html += `
                    <div class="text-center py-12">
                        <svg class="w-16 h-16 text-slate-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        </svg>
                        <h3 class="text-white text-lg font-medium mb-2">No Points of Interest Yet</h3>
                        <p class="text-slate-400">Right-click on the map to create your first Point of Interest.</p>
                    </div>
                `;
    } else {
        html += `<div class="space-y-2">`;

        pois.forEach(poi => {
            html += `
                        <div class="bg-slate-700/50 rounded-lg p-3 hover:bg-slate-700 transition-colors group">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-3 flex-1 cursor-pointer" onclick="document.getElementById('poi-manager-modal').classList.add('hidden'); openPOIModal('${poi.id}');">
                                    <div class="w-3 h-3 rounded-full border-2 border-white shadow-md flex-shrink-0" 
                                        style="background: #00D8FF;"></div>
                                    <div>
                                        <h5 class="text-white font-medium">${poi.name}</h5>
                                        <p class="text-xs text-slate-400">
                                            ${Number(poi.latitude).toFixed(5)}, ${Number(poi.longitude).toFixed(5)}
                                        </p>
                                    </div>
                                </div>
                                <div class="flex items-center space-x-2">
                                    <button onclick="event.stopPropagation(); MapViewer.goToPOI('${poi.id}', ${Number(poi.latitude)}, ${Number(poi.longitude)})" 
                                            class="p-1.5 text-slate-400 hover:text-sky-400 hover:bg-slate-600 rounded transition-all" 
                                            title="Go to Point of Interest on map">
                                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                                        </svg>
                                    </button>
                                    <svg class="w-5 h-5 text-slate-400 group-hover:text-white transition-colors cursor-pointer" 
                                        onclick="document.getElementById('poi-manager-modal').classList.add('hidden'); openPOIModal('${poi.id}');"
                                        fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                                    </svg>
                                </div>
                            </div>
                        </div>
                    `;
        });

        html += `</div>`;
    }

    html += '</div>';
    manager.html(html);
}