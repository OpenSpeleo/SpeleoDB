export function validateCell(value: string | null | undefined, column: string, isLastRow: boolean) {
    const v = (value ?? '').trim();
    if (column === 'depth') {
        if (v === '') return false;
        const n = parseFloat(v);
        return !isNaN(n) && isFinite(n) && n >= 0;
    }
    if (column === 'length') {
        if (isLastRow) return v === '';
        if (v === '') return false;
        const n = parseFloat(v);
        return !isNaN(n) && isFinite(n) && n >= 0;
    }
    if (column === 'azimuth') {
        if (isLastRow) return v === '';
        if (v === '') return false;
        const n = parseFloat(v);
        return !isNaN(n) && isFinite(n) && n >= 0 && n < 360;
    }
    if (['left', 'right', 'up', 'down'].includes(column)) {
        if (isLastRow) return v === '';
        if (v === '') return true;
        const n = parseFloat(v);
        return !isNaN(n) && isFinite(n) && n >= 0;
    }
    return true;
}

export function parseClipboardText(text: string) {
    // xls2dmp accepts clipboard data that may include an optional
    // leading "Station #" column which we strip so the shot
    // columns line up with COLUMNS.
    if (!text) return [];
    const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n').filter(l => l.trim());
    let rows = lines.map(line => {
        let parts = line.split('\t');
        if (parts.length === 1 && line.includes(',')) {
            parts = [];
            let current = '';
            let inQuotes = false;
            for (let i = 0; i < line.length; i++) {
                const char = line[i];
                const nextChar = line[i + 1];
                if (char === '"') {
                    if (inQuotes && nextChar === '"') {
                        current += '"'; i++;
                    } else {
                        inQuotes = !inQuotes;
                    }
                } else if (char === ',' && !inQuotes) {
                    parts.push(current); current = '';
                } else {
                    current += char;
                }
            }
            parts.push(current);
        }
        return parts.map(p => {
            let cleaned = p.replace(/^\uFEFF/, '').trim();
            if (cleaned.startsWith('"') && cleaned.endsWith('"')) {
                cleaned = cleaned.slice(1, -1);
            }
            return cleaned;
        });
    });
    if (rows.length > 0 && rows[0]!.length > 0) {
        const firstCell = rows[0]![0]!.trim();
        if (/^station/i.test(firstCell)) {
            const headerRow = rows[0]!;
            const stationColIndex = headerRow.findIndex(cell =>
                /^station\s*#?$/i.test(cell.trim())
            );
            rows.shift();
            if (stationColIndex !== -1) {
                rows = rows.map(row => {
                    const newRow = [...row];
                    newRow.splice(stationColIndex, 1);
                    return newRow;
                });
            }
        }
    }
    return rows.filter(row => row.some(cell => cell.trim() !== ''));
}
