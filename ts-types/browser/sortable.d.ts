import type Sortable from 'sortablejs';

declare global {
    interface Window { Sortable: typeof Sortable }
}
