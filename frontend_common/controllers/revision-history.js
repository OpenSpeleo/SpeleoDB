import { afterWindowLoad } from '../readiness.js';
import { sanitizeUrl } from '../../frontend_private/static/private/js/xss-helpers.js';

export async function init(context) {
    await afterWindowLoad();
    // Ensure the loading spinner is being displayed
        $("#loading_spinner").show();

        $.ajax({
            url: context.endpoint,
            type : "GET",
            dataType : "json",
            async: false,
            success: function(data){
                if (data && data.commits) {

                    // Iterate over each commit and append a new row to the table
                    data.commits.forEach(function (commit, index) {

                        if (commit.message == "[Automated] Project Creation" && commit.author_name == "SpeleoDB") {
                            return;  // Skip automated project creation commits
                        }

                        // === Build Mobile List Item ===
                        var $mobileItem = $('<div class="revision-item"></div>');

                        // Header with ID and actions
                        var $header = $('<div class="revision-header"></div>');
                        $header.append($('<div class="revision-id"></div>').text(commit.id.slice(0, 8)));

                        var $actions = $('<div class="revision-actions"></div>');

                        // Download dropdown for mobile
                        if (commit.formats && commit.formats.length > 0) {
                            var $downloadBtn = $('<div class="relative inline-flex" x-data="{ open: false }"><button class="text-indigo-400 hover:text-indigo-300" @click="open = !open"><svg class="w-6 h-6 fill-current" viewBox="0 0 24 24"><path d="M12 16l-4-4h3V4h2v8h3l-4 4zm-6 2h12v2H6v-2z"/></svg></button><div class="origin-top-right z-10 absolute top-full right-0 min-w-36 bg-slate-800 border border-slate-700 py-1.5 rounded-sm shadow-lg overflow-hidden mt-1" @click.outside="open = false" x-show="open" x-transition:enter="transition ease-out duration-200" x-transition:enter-start="opacity-0 -translate-y-2" x-transition:enter-end="opacity-100 translate-y-0" x-cloak><ul></ul></div></div>');
                            commit.formats.forEach(function(format) {
                                var $downloadItem = $('<li><a target="_blank" rel="noopener noreferrer" class="font-medium text-sm text-slate-300 hover:text-slate-200 flex py-1 px-3"></a></li>');
                                $downloadItem.find('a')
                                    .attr('href', sanitizeUrl(format.download_url))
                                    .text(format.name);
                                $downloadBtn.find('ul').append($downloadItem);
                            });
                            $actions.append($downloadBtn);
                        }

                        // Explorer link
                        var $explorerLink = $('<a class="text-indigo-400 hover:text-indigo-300"><svg class="w-6 h-6 stroke-current" stroke-width="1.5" fill="none" viewBox="2.25 3.25 19.5 18.5"><path d="M9 4h3l2 2h5a2 2 0 0 1 2 2v7a2 2 0 0 1 -2 2h-10a2 2 0 0 1 -2 -2v-9a2 2 0 0 1 2 -2" /><path d="M17 17v2a2 2 0 0 1 -2 2h-10a2 2 0 0 1 -2 -2v-9a2 2 0 0 1 2 -2h2" /></svg></a>');
                        $explorerLink.attr('href', sanitizeUrl(commit.url));
                        $actions.append($explorerLink);

                        $header.append($actions);
                        $mobileItem.append($header);

                        // Message
                        $mobileItem.append($('<div class="revision-message"></div>').text(commit.message));

                        // Meta info
                        var $meta = $('<div class="revision-meta"></div>');
                        var $author = $('<div class="revision-meta-item"><svg class="revision-meta-icon stroke-current" fill="none" viewBox="0 0 24 24" stroke-width="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg><span></span></div>');
                        $author.find('span').text(commit.author_name);
                        var $date = $('<div class="revision-meta-item"><svg class="revision-meta-icon stroke-current" fill="none" viewBox="0 0 24 24" stroke-width="2"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg><span></span></div>');
                        $date.find('span').text(commit.authored_date);
                        $meta.append($author, $date);
                        $mobileItem.append($meta);

                        // Append to mobile container
                        $('#mobile-revision-container').append($mobileItem);

                        // === Build Desktop Table Row ===
                        // Clone the hidden template row
                        var $row = $('#commit-template').clone();

                        // Remove the "ID" (to prevent deletion/cleanup) and make it unique
                        $row.removeAttr('id');

                        // Remove the "hidden" style (make it visible)
                        $row.removeAttr('style');

                        // Populate the row with commit data
                        // ---------------------------------------------------------------------
                        $row.find('td').eq(0).find('.font-medium').text(commit.id.slice(0, 8));    // Commit Short ID
                        $row.find('td').eq(1).find('.font-medium').text(commit.author_name);     // Author
                        $row.find('td').eq(2).find('.text-center').text(commit.authored_date);  // Date
                        $row.find('td').eq(3).find('.font-medium').text(commit.message);         // Message

                        // Adjusting all the links
                        // ---------------------------------------------------------------------

                        // 1. Project Explorer Link
                        var $link = $row.find("a.revision_explorer");
                        if ($link.length) {  // if found
                            $link.attr("href", sanitizeUrl(commit.url));
                        }

                        // 2. File Download Link
                        commit.formats.forEach(function(dl_format_data) {

                            var $download_link = $row.find('#format-download-template').clone();

                            // Ensure the element exists
                            if ($download_link.length === 0) {
                                console.error('#format-download-template not found.');
                                return;
                            }

                            // Modify the cloned template
                            $download_link
                                .removeAttr('id')    // Remove the ID to avoid duplicates
                                .removeAttr('style') // Make it visible
                                .find('a')
                                .attr("href", sanitizeUrl(dl_format_data.download_url))
                                .text(dl_format_data.name);

                            // Append the modified clone to the <ul>
                            $row.find('#format-download-container').append($download_link);
                        });

                        // Cleanup the format download template
                        $row.find('#format-download-template').remove();

                        // FINALLY: Append the populated row to the table body
                        // ---------------------------------------------------------------------
                        $('#commit-table-container').append($row);

                    });
                }
                else {
                    console.error(data.error);
                    return;
                }

                // Cleanup the template row
                $('#commit-template').remove();
            },
            error: function (textStatus, errorThrown) {
                console.error("ERROR: " + textStatus + " & " + errorThrown);
                return null;
            }
        });

        $("#loading_spinner").hide();
}
