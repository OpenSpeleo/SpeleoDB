/** Display permission labels without changing their API values. */
export function formatPermissionLabel(value: string | null | undefined): string {
    if (!value) return 'Unknown';
    const label = value.toLowerCase().split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    return label === 'Read And Write' ? 'Read & Write' : label;
}
