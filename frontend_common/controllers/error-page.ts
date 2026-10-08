import { initErrorPage } from '../../frontend_errors/static/ts/error.ts';

export async function init(): Promise<void> {
    await initErrorPage();
}
