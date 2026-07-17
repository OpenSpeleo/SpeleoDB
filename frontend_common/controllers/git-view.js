import { sanitizeUrl } from '../../frontend_private/static/private/js/xss-helpers.js';

export function init(context) {
    // Ensure the loading spinner is being displayed
       $("#loading_spinner").show();

       /**
        * jQuery ajax method with async = false, to fetch git tree data
        * @return {mix} - the git tree information
        */
       function fetch_git_tree() {
          return $.ajax({
             url: context.endpoint,
             type : "GET",
             dataType : "json",
             async : false,
             success: function(data){
                if (data && data.commit && data.project) {
                   $('#commit-author').text(data.commit.author_name + ": ");
                   $('#commit-message').text(data.commit.message);
                   $('#commit-hexsha_short').text(data.commit.hexsha_short);
                   $('#commit-dt_since').text(data.commit.dt_since);
                   $('#n-commits-count').text(data.project.n_commits);
                   return data;
                }
                else {
                   console.log("ERROR: " + (data && data.error ? data.error : "Unknown"));
                   return null;
                }
             },
             error: function (textStatus, errorThrown) {
                console.log("ERROR: " + textStatus + " & " + errorThrown);
                return null;
             }
          }).responseJSON;
       }

       /**
       * List files and folders based on the given path.
       * @param {string} path - The directory path to filter files. Root level if empty.
       * @returns {Object} - Dictionary with "files" and "folders".
       */
       function get_files_and_folders_at_path(path = "") {
          var result = {
             files: [],
             folders: []
          };

          const normalizedPath = path === "" ? path : path.endsWith("/") ? path : path + "/";

          globalGitTree.files.forEach(file => {
             if (path === "" || file.path.startsWith(normalizedPath)) {
                const relativePath = file.path.substring(normalizedPath.length);
                const parts = path == "" ? relativePath.split('/') : file.path.substring(normalizedPath.length).split("/");
                const folder_name = parts[0];

                if (parts.length === 1) {
                   // We are processing a file
                   result.files.push(file);
                }
                else {
                   const index = result.folders.findIndex(folder => folder.name === folder_name);
                   if (index !== -1) {
                      // Use moment.js to parse the datetime string with custom format
                      // Let's find if there's a newer commit.
                      const currentDate = window.moment(result.folders[index].datetime, "YYYY/MM/DD HH:mm");
                      const newDate = window.moment(file.commit.authored_date, "YYYY/MM/DD HH:mm");

                      if (newDate.isAfter(currentDate)) {
                         result.folders[index] = {
                            ...result.folders[index], // copies all existing properties
                            message: file.commit.message,
                            dt_since: file.commit.dt_since,
                            commit_url: file.commit.url,
                            datetime: file.commit.authored_date
                         };
                     }
                   } else {
                      result.folders.push({
                         name: folder_name,
                         path: `${normalizedPath}${folder_name}`,
                         message: file.commit.message,
                         dt_since: file.commit.dt_since,
                         commit_url: file.commit.url,
                         datetime: file.commit.authored_date
                      });
                   }
                }
             }
          });

          if (path != "") {
             // Add a reference to the parent directory
             const parentPath = path.split('/').slice(0, -1).join('/') || "/";
             result.folders.unshift({
                 name: "..",
                 path: parentPath == "/" ? "" : parentPath
             });
          }

          // Sort files alphabetically by their "name" property
          result.folders.sort((a, b) => {
             if (a.name < b.name) return -1;
             if (a.name > b.name) return 1;
             return 0;
          });
          result.files.sort((a, b) => a.name.localeCompare(b.name));

          return result;
       }

       // Function to refresh UX
       function refresh_ux(path="") {

          // Empty the Git View
          $('#git-viewer-container').empty();

          const $githeader = $("#row-template-currentdir").clone();
          // Remove the "ID" (to prevent deletion/cleanup) and make it unique
          $githeader.removeAttr('id');
          // Remove the "hidden" style (make it visible)
          $githeader.removeAttr('style');

          // Set the folder name:
          $githeader.find(".current-gitfolder-name").text("Current Folder: /" + path);
          $('#git-viewer-container').append($githeader);

          // Fetch the files & folders at the path requested
          const data = get_files_and_folders_at_path(path);

          // Populate the folders
          data.folders.forEach(function(folder) {
             const $folder_row = $('#row-template-folder').clone();

             // Remove the "ID" (to prevent deletion/cleanup) and make it unique
             $folder_row.removeAttr('id');

             // Remove the "hidden" style (make it visible)
             $folder_row.removeAttr('style');

             // Folder Related Content
             var clickable_link = $folder_row.find(".gitfolder-link");
             clickable_link.attr("data-path", folder.path);
             clickable_link.on('click', function() {
                // Trigger the refresh_ux function with the path from the clicked link
                refresh_ux($(this).attr('data-path'));
             });

             $folder_row.find(".gitfolder-name").text(folder.name);
             $folder_row.find(".commit-message").attr("href", sanitizeUrl(folder.commit_url)).text(folder.message);
             $folder_row.find(".commit-time-ago").attr("href", sanitizeUrl(folder.commit_url)).text(folder.dt_since);

             // FINALLY: Append the populated row to the table body
             // ---------------------------------------------------------------------
             $('#git-viewer-container').append($folder_row);
          });

          // Populate the files
          data.files.forEach(function(file) {
             const $file_row = $('#row-template-file').clone();

             // Remove the "ID" (to prevent deletion/cleanup) and make it unique
             $file_row.removeAttr('id');

             // Remove the "hidden" style (make it visible)
             $file_row.removeAttr('style');

             // File Related Content
             $file_row.find(".download-file-link").attr("href", sanitizeUrl(file.download_url));
             $file_row.find(".download-file-name").text(file.name);
             $file_row.find(".file-size-link").attr("href", sanitizeUrl(file.download_url));
             $file_row.find(".file-size").text(file.size);

             // Commit Related Content
             $file_row.find(".commit-message").attr("href", sanitizeUrl(file.commit.url)).text(file.commit.message);
             $file_row.find(".commit-time-ago").attr("href", sanitizeUrl(file.commit.url)).text(file.commit.dt_since);

             // FINALLY: Append the populated row to the table body
             // ---------------------------------------------------------------------
             $('#git-viewer-container').append($file_row);
          });
       }

       // Fetch the Git Tree and store it as a constant for later re-use
       const globalGitTree = fetch_git_tree();

       if (globalGitTree && Array.isArray(globalGitTree.files)) {
          refresh_ux("");
       }

       $("#loading_spinner").hide();
}
