const chokidar = require('chokidar');
const { execSync } = require('child_process');
const path = require('path');

console.log('Starting JavaScript file watcher...');

// Watch JavaScript source files
const jsWatcher = chokidar.watch('./src/js/**/*.js', {
    ignored: /(^|[\/\\])\../, // ignore dotfiles
    persistent: true
});

// Watch for changes
jsWatcher
    .on('change', (filePath) => {
        console.log(`\n📝 File changed: ${filePath}`);
        rebuildJs();
    })
    .on('add', (filePath) => {
        console.log(`\n➕ File added: ${filePath}`);
        rebuildJs();
    })
    .on('unlink', (filePath) => {
        console.log(`\n🗑️  File removed: ${filePath}`);
        rebuildJs();
    })
    .on('ready', () => {
        console.log('👀 Watching for JavaScript changes...');
        console.log('   - Watching: ./src/js/**/*.js');
        console.log('   - Press Ctrl+C to stop\n');
    })
    .on('error', (error) => {
        console.error('❌ Watcher error:', error);
    });

function rebuildJs() {
    try {
        console.log('🔨 Rebuilding JavaScript...');
        execSync('node scripts/build.js', { 
            stdio: 'inherit',
            cwd: path.join(__dirname, '..')
        });
        console.log('✅ JavaScript rebuild completed\n');
    } catch (error) {
        console.error('❌ JavaScript rebuild failed:', error.message);
    }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
    console.log('\n👋 Stopping file watcher...');
    jsWatcher.close().then(() => {
        console.log('✅ File watcher stopped');
        process.exit(0);
    });
});

process.on('SIGTERM', () => {
    console.log('\n👋 Stopping file watcher...');
    jsWatcher.close().then(() => {
        console.log('✅ File watcher stopped');
        process.exit(0);
    });
});