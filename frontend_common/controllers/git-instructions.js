import { afterWindowLoad } from '../readiness.js';

export async function init() {
    await afterWindowLoad();
    $('#btn_show_git_instructions').on('click', function () {
        $('#modal_git_instructions').css('display', 'flex');
        return false;
    });
    $('.btn_close').on('click', function () {
        if ($('#modal_git_instructions').is(':visible')) $('#modal_git_instructions').hide();
    });
}
