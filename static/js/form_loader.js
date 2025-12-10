/**
 * form_loader.js
 * 1. Prevents double-submission.
 * 2. Shows a spinner for standard forms.
 * 3. Shows a PROGRESS BAR for forms with file uploads.
 */

document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    
    // Inject Styles for the Progress Modal
    const style = document.createElement('style');
    style.innerHTML = `
        #upload-progress-modal {
            position: fixed; inset: 0; background: rgba(0,0,0,0.6); 
            display: none; align-items: center; justify-content: center; z-index: 9999;
            backdrop-filter: blur(4px);
        }
        #upload-progress-box {
            background: white; padding: 20px; border-radius: 12px; 
            width: 90%; max-width: 400px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
            font-family: 'Poppins', sans-serif;
        }
        .progress-track {
            background-color: #e5e7eb; border-radius: 9999px; height: 16px; 
            width: 100%; overflow: hidden; margin-top: 10px;
        }
        .progress-fill {
            background-color: #2563eb; height: 100%; width: 0%; 
            transition: width 0.2s ease; border-radius: 9999px;
        }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    `;
    document.head.appendChild(style);

    // Create Progress Modal DOM
    const modal = document.createElement('div');
    modal.id = 'upload-progress-modal';
    modal.innerHTML = `
        <div id="upload-progress-box">
            <h3 style="margin:0 0 10px 0; font-weight:600; color:#1f2937;">Uploading Files...</h3>
            <div style="display:flex; justify-content:space-between; margin-bottom:5px; font-size:0.875rem; color:#4b5563;">
                <span id="progress-text">Preparing...</span>
                <span id="progress-percent">0%</span>
            </div>
            <div class="progress-track">
                <div id="progress-bar-fill" class="progress-fill"></div>
            </div>
            <p style="margin-top:10px; font-size:0.75rem; color:#6b7280; text-align:center;">Please do not close this window.</p>
        </div>
    `;
    document.body.appendChild(modal);

    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            const submitter = event.submitter;

            // Only proceed if a submit button triggered the event
            if (submitter && submitter.tagName === 'BUTTON' && submitter.type === 'submit') {
                event.preventDefault(); // Stop standard submit immediately

                // Disable UI
                const allButtons = form.querySelectorAll('button[type="submit"]');
                allButtons.forEach(btn => {
                    btn.disabled = true;
                    btn.style.opacity = '0.75';
                    btn.style.cursor = 'not-allowed';
                });

                // Check if form has files
                const hasFiles = form.querySelector('input[type="file"]');

                if (hasFiles) {
                    // === SCENARIO A: AJAX UPLOAD WITH PROGRESS BAR ===
                    handleFileUpload(form, submitter);
                } else {
                    // === SCENARIO B: STANDARD SPINNER (No files) ===
                    // Add hidden input to maintain button value
                    const input = document.createElement('input');
                    input.type = 'hidden'; 
                    input.name = submitter.name; 
                    input.value = submitter.value;
                    form.appendChild(input);

                    // Show Spinner on Button
                    const spinner = `
                        <svg aria-hidden="true" style="display:inline; width:1em; height:1em; margin-right:5px; vertical-align: -0.125em; animation:spin 1s linear infinite;" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor" opacity="0.2"/>
                            <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="currentColor"/>
                        </svg>
                    `;
                    submitter.innerHTML = `${spinner} Processing...`;
                    form.submit();
                }
            }
        });
    });

    function handleFileUpload(form, submitter) {
        // Show Modal
        const modal = document.getElementById('upload-progress-modal');
        const fill = document.getElementById('progress-bar-fill');
        const text = document.getElementById('progress-text');
        const percent = document.getElementById('progress-percent');
        
        modal.style.display = 'flex';

        // Prepare Data
        const formData = new FormData(form);
        // Append submitter manually since FormData doesn't include the clicked button
        formData.append(submitter.name, submitter.value);

        const xhr = new XMLHttpRequest();
        xhr.open(form.method, form.action, true);

        // Track Progress
        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                fill.style.width = percentComplete + '%';
                percent.textContent = percentComplete + '%';
                
                if (percentComplete < 50) text.textContent = "Uploading...";
                else if (percentComplete < 99) text.textContent = "Almost there...";
                else text.textContent = "Processing...";
            }
        };

        // Handle Response
        xhr.onload = function() {
            if (xhr.status === 200) {
                // If the backend redirected us to a new URL, follow it.
                // If the backend rendered a template (like an error page), replace the document.
                if (xhr.responseURL && xhr.responseURL !== window.location.href) {
                    window.location.href = xhr.responseURL;
                } else {
                    // Replace current page content with response (useful for validation errors)
                    document.open();
                    document.write(xhr.responseText);
                    document.close();
                    
                    // Re-hide modal if we are staying on page (e.g. error)
                    // Note: document.write usually kills the old script context, 
                    // so the modal might disappear naturally.
                }
            } else {
                alert('An error occurred during upload. Please try again.');
                modal.style.display = 'none';
                // Re-enable buttons
                form.querySelectorAll('button').forEach(btn => btn.disabled = false);
            }
        };

        xhr.onerror = function() {
            alert('Network error. Please check your connection.');
            modal.style.display = 'none';
            form.querySelectorAll('button').forEach(btn => btn.disabled = false);
        };

        xhr.send(formData);
    }
});
