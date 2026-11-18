import { v2UserDonationCampaignsDismissCreate } from '@speleodb/api';
import { apiData, webApiOptions } from '../api/client.ts';

/** data-campaign-* hooks own opening, dismissal, donation, story navigation and explicit retry actions. */
export function init(context: { campaignId: string; shouldInvite: boolean }) {
    const root = document.querySelector<HTMLElement>('.donation-dialog');
    const overview = root?.querySelector<HTMLElement>('[data-campaign-overview]');
    const story = root?.querySelector<HTMLElement>('[data-campaign-story]');
    const storyLink = root?.querySelector<HTMLButtonElement>('[data-campaign-story-open]');
    let overviewScroll = 0;
    function showOverview(restoreFocus: boolean) {
        if (!root || !overview || !story) return;
        overview.hidden = false;
        story.hidden = true;
        root.setAttribute('aria-labelledby', 'campaign-heading');
        if (restoreFocus) {
            storyLink?.focus({ preventScroll: true });
            root.scrollTop = overviewScroll;
        }
    }
    storyLink?.addEventListener('click', () => {
        if (!root || !overview || !story) return;
        overviewScroll = root.scrollTop;
        overview.hidden = true;
        story.hidden = false;
        root.setAttribute('aria-labelledby', 'campaign-story-heading');
        root.scrollTop = 0;
        story.querySelector<HTMLElement>('h2')?.focus({ preventScroll: true });
    });
    root?.querySelector('[data-campaign-story-back]')?.addEventListener('click', () => showOverview(true));
    const dialog = document.querySelector<HTMLDialogElement>('#donation-campaign');
    const error = document.querySelector<HTMLElement>('#campaign-save-error');
    if (!dialog || !error) return;
    let saved = false;
    let saving = false;
    let returnFocus = document.querySelector<HTMLElement>('#dashboard-heading');
    async function persist() {
        if (saved || saving) return;
        saving = true;
        error!.hidden = true;
        try {
            await apiData(v2UserDonationCampaignsDismissCreate(
                context.campaignId, undefined, webApiOptions(),
            ));
            saved = true;
        } catch {
            error!.hidden = false;
        } finally {
            saving = false;
        }
    }
    function dismiss() {
        if (dialog!.open) dialog!.close();
        returnFocus?.focus();
        void persist();
    }
    function open(invoker: HTMLElement | null) {
        if (document.querySelector('dialog[open]')) return;
        returnFocus = invoker;
        saved = false;
        showOverview(false);
        dialog!.showModal();
        dialog!.querySelector<HTMLElement>('h2')?.focus();
    }
    document.querySelectorAll<HTMLElement>('[data-campaign-open]').forEach(button => {
        button.addEventListener('click', () => open(button));
    });
    document.querySelectorAll('[data-campaign-dismiss], [data-campaign-donate]').forEach(button => {
        button.addEventListener('click', dismiss);
    });
    document.querySelector('[data-campaign-retry]')?.addEventListener('click', () => { void persist(); });
    dialog.addEventListener('cancel', event => { event.preventDefault(); dismiss(); });
    dialog.addEventListener('click', event => {
        const bounds = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right
            || event.clientY < bounds.top || event.clientY > bounds.bottom)) dismiss();
    });
    // A focused control means the user has already begun working while modules loaded.
    if (context.shouldInvite && (document.activeElement === document.body || !document.activeElement)) {
        open(returnFocus);
    }
}
