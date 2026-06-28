import { afterWindowLoad } from '../readiness.js';
import { showAjaxErrorModal } from '../../frontend_private/static/private/js/forms/ajax_errors.js';
import { escapeHtml } from '../../frontend_private/static/private/js/xss-helpers.js';

export async function init(context) {
    await afterWindowLoad();
    $("body").click(function() {
              if ($("#modal_success").is(":visible")) {
                $("#modal_success").hide();
              }
              if ($("#modal_error").is(":visible")) {
                $("#modal_error").hide();
              }
            });

            let filesArray = [];

            $('#dropzone').on('dragover', function(e) {
                e.preventDefault();
                e.stopPropagation();
                $(this).removeClass('border-slate-700 bg-srgb-slate-700-30');
                $(this).addClass('border-srgb-amber-500-50 bg-srgb-amber-400-10');
            });
            
            $('#dropzone').on('dragleave', function(e) {
                e.preventDefault();
                e.stopPropagation();
                $(this).removeClass('border-srgb-amber-500-50 bg-srgb-amber-400-10');
                $(this).addClass('border-slate-700 bg-srgb-slate-700-30');
            });
            
            $('#dropzone').on('drop', function(e) {
                e.preventDefault();
                e.stopPropagation();
                $(this).removeClass('border-srgb-amber-500-50 bg-srgb-amber-400-10');
                let newFiles = Array.from(e.originalEvent.dataTransfer.files);
                handleFiles(newFiles);
            });
            
            $('#dropzone').on('click', function(e) {
                e.preventDefault();
                $('#artifact').click();
            });
            
            $('#artifact').on('change', function(e) {
                let newFiles = Array.from(this.files);
                handleFiles(newFiles);
                // Clear the input field to allow the same file to be selected again
                $('#artifact').val('');
            });
            
            function handleFiles(newFiles) {
                // Verify the max number of files:
                if (filesArray.length + newFiles.length > context.maxFiles) {
                    $("#modal_error_txt").text("You can upload a maximum of " + context.maxFiles + " files at a time.");
                    $("#modal_error").css("display", "flex");
                    return false;
                }
            
                // Verify each file is under the max size [2Mb]
                let totalSize = filesArray.reduce((acc, file) => acc + file.size, 0);
                for (let file of newFiles) {
                    totalSize += file.size;
                    if (file.size > context.maxFileSizeMb * 1024 * 1024) { // Check if any file exceeds limit
                        $("#modal_error_txt").text("File too large: " + file.name + " (Max " + context.maxFileSizeMb + " Mb).");
                        $("#modal_error").css("display", "flex");
                        return false;
                    }
                }
            
                // Verify the total size is under the max size [50Mb]
                if (totalSize > context.maxTotalSizeMb * 1024 * 1024) {
                    $("#modal_error_txt").text("Total upload size exceeds " + context.maxTotalSizeMb + " Mb.");
                    $("#modal_error").css("display", "flex");
                    return false;
                }
            
                // Add new files to the array
                filesArray = filesArray.concat(newFiles);
            
                // If it was done with drag & drop
                $('#dropzone').removeClass('border-srgb-amber-500-50 bg-srgb-amber-400-10');
            
                // If it was done with filepicker
                $('#dropzone').removeClass('hover bg-srgb-slate-700-30 border-slate-700');
                $('#dropzone').addClass('bg-srgb-emerald-500-10 border-emerald-300');
            
                $("#icon_waiting_for_file").hide();
                $('#dropzone').addClass('dropped');
            
                updateFileList();
            }
            
            function updateFileList() {
                if (filesArray.length === 0) {
                    // Reset to initial state
                    $('#dropzone').removeClass('bg-srgb-emerald-500-10 border-emerald-300 dropped');
                    $('#dropzone').addClass('bg-srgb-slate-700-30 border-slate-700');
                    $("#icon_waiting_for_file").show();
                    $('#dropzone label').html('Please upload up to ' + context.maxFiles + ' files, each under ' + context.maxFileSizeMb + ' Mb [Total under ' + context.maxTotalSizeMb + ' Mb].');
                } else {
                    let fileNames = filesArray.map((file, index) => 
                        `<div>
                            - ${escapeHtml(file.name)} <span class="remove-file" data-index="${index}" style="color: red; font-size: 20px; cursor: pointer;">&times;</span>
                        </div>`
                    ).join("");
                    $('#dropzone label').html("<b>** Files to upload **</b><hr class='my-4'>" + fileNames);
            
                    $('.remove-file').on('click', function(event) {
                        event.stopPropagation(); // Prevent the file picker from opening
                        event.preventDefault(); // Prevent the default behavior
                        let index = $(this).data('index');
                        filesArray.splice(index, 1);
                        updateFileList();
                    });
                }
            }

            $('#message').on('input', function() {
                $(this).removeClass('border-rose-600');
            });

            $('#btn_submit').click(function() {
              if ($('#message').val().trim() === "") {
                $("#modal_error_txt").text("The revision title cannot be empty.");
                $("#modal_error").css('display', 'flex');
                $('#message').addClass('border-rose-600');
                return false;
              }

              var csrftoken = $('input[name^=csrfmiddlewaretoken]').val();

              var formData = new FormData();
              filesArray.forEach((file, index) => {
                formData.append("artifact", file);
              });
              formData.append("message", $('#message').val());

              $("#error_div").hide();
              $("#success_div").hide();

              $.ajax({
                url: context.endpoint,
                method: "PUT",
                data: formData,
                contentType: false,
                processData: false,
                cache: false,
                beforeSend: function(xhr) {
                  xhr.setRequestHeader("X-CSRFToken", csrftoken);

                  if ($("#message").val().length > 125) {
                    $("#modal_error_txt").text("The `message` is too long. Maximum 125 characters.");
                    $("#modal_error").css('display', 'flex');
                    return false;
                  }

                  $("#loading_spinner").show();

                  return true;

                },
                success: function(data, textStatus, xhr) {
                  $("#loading_spinner").hide();

                  if (xhr.status === 304) {
                    $("#modal_error_txt").text("The file(s) uploaded is/are identical to the one(s) currently stored.");
                    $("#modal_error").css('display', 'flex');
                  } else {
                    $("#modal_success_txt").html("The file(s) has/have been succesfully uploaded.");
                    $("#modal_success").css('display', 'flex');

                    window.setTimeout(function() {
                      // Redirect to project revisions
                      window.location.href = data.browser_url;
                    }, 2000);
                  }
                },
                error: function(data) {
                  $("#loading_spinner").hide();
                  showAjaxErrorModal(data);
                }
              });
              return false; // prevent default
            });
}
