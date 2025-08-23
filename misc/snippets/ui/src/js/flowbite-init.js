// Initialize Flowbite components
import { initFlowbite } from 'flowbite';

// Ensure DOM is ready before accessing document.body
function addBodyEventListener(event, handler) {
    if (document.body) {
        document.body.addEventListener(event, handler);
    } else {
        document.addEventListener('DOMContentLoaded', function() {
            document.body.addEventListener(event, handler);
        });
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    if (typeof initFlowbite === 'function') {
        initFlowbite();
    }
});

// Re-initialize after HTMX swaps
addBodyEventListener('htmx:afterSwap', function() {
    if (typeof initFlowbite === 'function') {
        initFlowbite();
    }
});

// Re-initialize after Alpine.js updates
document.addEventListener('alpine:init', () => {
    // Ensure Flowbite works with Alpine.js
    if (typeof initFlowbite === 'function') {
        initFlowbite();
    }
});

// Re-initialize when new content is added dynamically
addBodyEventListener('htmx:afterSettle', function() {
    if (typeof initFlowbite === 'function') {
        initFlowbite();
    }
});

// Handle modal events
document.addEventListener('alpine:init', () => {
    Alpine.data('flowbiteModal', () => ({
        show: false,
        
        open() {
            this.show = true;
            document.body.classList.add('overflow-hidden');
        },
        
        close() {
            this.show = false;
            document.body.classList.remove('overflow-hidden');
        },
        
        toggle() {
            this.show ? this.close() : this.open();
        }
    }));
});

// Handle dropdown events
document.addEventListener('alpine:init', () => {
    Alpine.data('flowbiteDropdown', () => ({
        open: false,
        
        toggle() {
            this.open = !this.open;
        },
        
        close() {
            this.open = false;
        }
    }));
});

// Handle toast notifications
document.addEventListener('alpine:init', () => {
    Alpine.data('flowbiteToast', () => ({
        show: true,
        
        dismiss() {
            this.show = false;
        },
        
        autoDismiss(delay = 5000) {
            setTimeout(() => {
                this.dismiss();
            }, delay);
        }
    }));
});

// Export for use in other modules
window.FlowbiteInit = {
    init: initFlowbite,
    reinit: () => {
        initFlowbite();
    }
};