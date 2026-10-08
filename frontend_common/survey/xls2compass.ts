export function validateCell(value: string | null | undefined, column: string, isLastRow: boolean) {
    const v = (value ?? '').trim();
    if (column === 'station') {
        return v !== '';
    }
    if (column === 'depth') {
        if (v === '') return false;
        const n = Number(v);
        return !isNaN(n) && isFinite(n) && n >= 0;
    }
    if (column === 'length') {
        if (isLastRow) return v === '';
        if (v === '') return false;
        const n = Number(v);
        return !isNaN(n) && isFinite(n) && n >= 0;
    }
    if (column === 'azimuth') {
        if (isLastRow) return v === '';
        if (v === '') return false;
        const n = Number(v);
        return !isNaN(n) && isFinite(n) && n >= 0 && n < 360;
    }
    if (['left', 'right', 'up', 'down'].includes(column)) {
        if (isLastRow) return v === '';
        if (v === '') return true;
        const n = Number(v);
        return !isNaN(n) && isFinite(n) && n >= 0;
    }
    if (['flags', 'comment'].includes(column)) {
        if (isLastRow) return v === '';
        return true;
    }
    return true;
}

export function parseClipboardText(text: string) {
    if (!text) return [];
    const lines = text.replace(/\r/g, '\n').split(/\n/).filter(l => l.trim());
    const rows = lines.map(line => {
        let parts = line.split('\t');
        if (parts.length === 1) parts = line.split(',');
        return parts.map(p => p.replace(/^\uFEFF/, '').trim());
    });
    if (rows.length > 0 && /station/i.test(rows[0]![0]!)) rows.shift();
    return rows;
}
