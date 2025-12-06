/**
 * form_loader.js
 * Prevents double-submission of forms by disabling the submit button
 * and showing a loading spinner immediately upon click.
 */

document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            // "event.submitter" identifies the specific button that was clicked
            const submitter = event.submitter;
            
            // Only proceed if a submit button triggered the event
            if (submitter && submitter.tagName === 'BUTTON' && submitter.type === 'submit') {
                
                // 1. Prevent the default submission temporarily to manipulate data
                event.preventDefault();
                
                // 2. Create a hidden input to preserve the button's name/value
                //    (Because disabled buttons are NOT sent in the POST request, 
                //     we must simulate the button's value manually)
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = submitter.name;
                input.value = submitter.value;
                form.appendChild(input);
                
                // 3. Visual Feedback: Create a Spinner
                // Simple SVG Spinner (White/CurrentColor)
                const spinner = `
                    <svg aria-hidden="true" role="status" style="display:inline; width:1em; height:1em; margin-right:5px; vertical-align: -0.125em; animation:spin 1s linear infinite;" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor" opacity="0.2"/>
                        <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="currentColor"/>
                    </svg>
                `;

                // Update button content
                submitter.innerHTML = `${spinner} Processing...`;
                
                // 4. Disable all submit buttons in this specific form to prevent conflicts
                //    (We use setTimeout 0 to let the browser repaint before the heavy request starts)
                const allButtons = form.querySelectorAll('button[type="submit"]');
                allButtons.forEach(btn => {
                    btn.disabled = true;
                    btn.style.opacity = '0.75';
                    btn.style.cursor = 'not-allowed';
                });

                // 5. Submit the form programmatically now that data is safe
                form.submit();
            }
        });
    });

    // Inject required keyframes for animation if not present
    if (!document.getElementById('spinner-style')) {
        const style = document.createElement('style');
        style.id = 'spinner-style';
        style.innerHTML = `
            @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        `;
        document.head.appendChild(style);
    }
});