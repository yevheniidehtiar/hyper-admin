const fs = require('fs');
const path = require('path');

console.log('Building JavaScript assets...');

// Ensure dist directories exist
const distJsPath = path.join(__dirname, '../dist/js');
const distCssPath = path.join(__dirname, '../dist/css');

if (!fs.existsSync(distJsPath)) {
    fs.mkdirSync(distJsPath, { recursive: true });
}

if (!fs.existsSync(distCssPath)) {
    fs.mkdirSync(distCssPath, { recursive: true });
}

try {
    // Copy Flowbite JS to dist
    const flowbitePath = path.join(__dirname, '../node_modules/flowbite/dist/flowbite.min.js');
    if (fs.existsSync(flowbitePath)) {
        fs.copyFileSync(flowbitePath, path.join(distJsPath, 'flowbite.min.js'));
        console.log('✓ Copied Flowbite JavaScript');
    } else {
        console.warn('⚠ Flowbite JavaScript not found, run npm install first');
    }

    // Bundle custom JS (for now, just copy the init script)
    // In a more complex setup, you might use a bundler like esbuild or webpack
    const initScriptPath = path.join(__dirname, '../src/js/flowbite-init.js');
    if (fs.existsSync(initScriptPath)) {
        let initScript = fs.readFileSync(initScriptPath, 'utf8');
        
        // Simple transform: remove ES6 import and use global Flowbite
        initScript = initScript.replace(
            "import { initFlowbite } from 'flowbite';",
            "// Using global initFlowbite from flowbite.min.js\nconst initFlowbite = window.initFlowbite;"
        );
        
        // Add error handling
        initScript = `
// Flowbite Integration for SQLAdmin-HTMX
(function() {
    'use strict';
    
    ${initScript}
    
    // Fallback if Flowbite is not loaded
    if (typeof initFlowbite === 'undefined') {
        console.warn('Flowbite not loaded, some components may not work properly');
        window.FlowbiteInit = {
            init: () => console.warn('Flowbite not available'),
            reinit: () => console.warn('Flowbite not available')
        };
    }
})();
`;
        
        fs.writeFileSync(path.join(distJsPath, 'main.js'), initScript);
        console.log('✓ Built main.js');
    } else {
        console.error('✗ Flowbite init script not found');
    }

    // Create a combined bundle for easier inclusion
    const flowbiteJs = fs.existsSync(path.join(distJsPath, 'flowbite.min.js')) 
        ? fs.readFileSync(path.join(distJsPath, 'flowbite.min.js'), 'utf8')
        : '';
    const mainJs = fs.existsSync(path.join(distJsPath, 'main.js'))
        ? fs.readFileSync(path.join(distJsPath, 'main.js'), 'utf8')
        : '';
    
    if (flowbiteJs && mainJs) {
        const bundledJs = `${flowbiteJs}\n\n${mainJs}`;
        fs.writeFileSync(path.join(distJsPath, 'bundle.js'), bundledJs);
        console.log('✓ Created bundle.js');
        
        // Copy bundle.js to sqladmin/statics/js/ directory
        const sqlAdminJsPath = path.join(__dirname, '../../sqladmin/statics/js');
        if (!fs.existsSync(sqlAdminJsPath)) {
            fs.mkdirSync(sqlAdminJsPath, { recursive: true });
        }
        
        fs.copyFileSync(
            path.join(distJsPath, 'bundle.js'),
            path.join(sqlAdminJsPath, 'bundle.js')
        );
        console.log('✓ Copied bundle.js to sqladmin/statics/js/');
    }

    console.log('JavaScript build completed successfully!');

} catch (error) {
    console.error('Build failed:', error.message);
    process.exit(1);
}