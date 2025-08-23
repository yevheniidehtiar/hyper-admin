# SQLAdmin-HTMX UI Build System

Modern UI build system for SQLAdmin-HTMX with Flowbite integration, built on Tailwind CSS and npm tooling.

## 🎯 Overview

This UI build system provides:
- **Flowbite UI Components**: Complete access to 100+ Flowbite components
- **Tailwind CSS**: Utility-first CSS framework with custom extensions
- **Build Pipeline**: Automated CSS/JS compilation and optimization
- **Development Workflow**: Watch mode for rapid development
- **HTMX Integration**: Seamless compatibility with HTMX dynamic content
- **Alpine.js Support**: Works with existing Alpine.js components

## 📁 Directory Structure

```
ui/
├── package.json              # npm dependencies and scripts
├── tailwind.config.js        # Tailwind CSS + Flowbite configuration
├── postcss.config.js         # PostCSS configuration
├── src/                      # Source files
│   ├── css/
│   │   ├── main.css         # Main CSS entry point
│   │   ├── components/      # Component-specific styles
│   │   │   ├── forms.css    # Form components
│   │   │   ├── tables.css   # Table components
│   │   │   └── modals.css   # Modal components
│   │   └── pages/           # Page-specific styles (empty)
│   └── js/
│       └── flowbite-init.js # Flowbite initialization & HTMX integration
├── dist/                    # Built files (auto-generated)
│   ├── css/
│   │   └── main.css        # Compiled CSS (~44KB)
│   └── js/
│       ├── bundle.js       # Combined Flowbite + init (~138KB)
│       ├── flowbite.min.js # Flowbite library
│       └── main.js         # Initialization script
├── scripts/                # Build scripts
│   ├── build.js           # Production build script
│   └── watch.js           # Development watch script
└── node_modules/          # npm dependencies (gitignored)
```

## 🚀 Quick Start

### Prerequisites
- Node.js 16+ and npm
- SQLAdmin-HTMX project setup

### Installation

```bash
# Navigate to UI directory
cd ui

# Install dependencies
npm install
```

### Development Workflow

```bash
# Start development mode (watch for changes)
npm run dev

# Or run individual commands:
npm run watch:css    # Watch CSS changes only
npm run watch:js     # Watch JS changes only
```

### Production Build

```bash
# Build optimized assets for production
npm run build

# Or run individual builds:
npm run build:css    # Build CSS only
npm run build:js     # Build JS only
```

## 📋 Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start development mode (watch CSS + JS) |
| `npm run build` | Build production assets (CSS + JS) |
| `npm run build:css` | Compile and minify CSS |
| `npm run build:js` | Bundle JavaScript files |
| `npm run watch` | Alias for `npm run dev` |
| `npm run watch:css` | Watch CSS files for changes |
| `npm run watch:js` | Watch JS files for changes |

## 🎨 Using Flowbite Components

### AI, LLM
Please check instructions about components here: https://raw.githubusercontent.com/themesberg/flowbite/refs/heads/main/llms.txt


### Basic Components

```html
<!-- Flowbite Button -->
<button type="button" class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 focus:outline-none">
    Primary Button
</button>

<!-- Flowbite Input -->
<div class="mb-6">
    <label for="email" class="block mb-2 text-sm font-medium text-gray-900">Email</label>
    <input type="email" id="email" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" placeholder="name@example.com" required>
</div>

<!-- Flowbite Card -->
<div class="max-w-sm bg-white border border-gray-200 rounded-lg shadow">
    <div class="p-5">
        <h5 class="mb-2 text-2xl font-bold tracking-tight text-gray-900">Card Title</h5>
        <p class="mb-3 font-normal text-gray-700">Card content goes here.</p>
    </div>
</div>
```

### Advanced Components

```html
<!-- Flowbite Modal -->
<div id="default-modal" tabindex="-1" aria-hidden="true" class="hidden overflow-y-auto overflow-x-hidden fixed top-0 right-0 left-0 z-50 justify-center items-center w-full md:inset-0 h-[calc(100%-1rem)] max-h-full">
    <div class="relative p-4 w-full max-w-2xl max-h-full">
        <div class="relative bg-white rounded-lg shadow">
            <div class="flex items-center justify-between p-4 md:p-5 border-b rounded-t">
                <h3 class="text-xl font-semibold text-gray-900">Modal Title</h3>
                <button type="button" class="text-gray-400 bg-transparent hover:bg-gray-200 hover:text-gray-900 rounded-lg text-sm w-8 h-8 ms-auto inline-flex justify-center items-center" data-modal-hide="default-modal">
                    <svg class="w-3 h-3" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 14 14">
                        <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m1 1 6 6m0 0 6 6M7 7l6-6M7 7l-6 6"/>
                    </svg>
                </button>
            </div>
            <div class="p-4 md:p-5 space-y-4">
                <p class="text-base leading-relaxed text-gray-500">Modal content</p>
            </div>
        </div>
    </div>
</div>

<!-- Flowbite Dropdown -->
<button id="dropdownDefaultButton" data-dropdown-toggle="dropdown" class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center inline-flex items-center" type="button">
    Dropdown button
    <svg class="w-2.5 h-2.5 ms-3" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 10 6">
        <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m1 1 4 4 4-4"/>
    </svg>
</button>
<div id="dropdown" class="z-10 hidden bg-white divide-y divide-gray-100 rounded-lg shadow w-44">
    <ul class="py-2 text-sm text-gray-700" aria-labelledby="dropdownDefaultButton">
        <li><a href="#" class="block px-4 py-2 hover:bg-gray-100">Dashboard</a></li>
        <li><a href="#" class="block px-4 py-2 hover:bg-gray-100">Settings</a></li>
    </ul>
</div>
```

## 🔧 Custom Styling

### Adding Component Styles

Create new component styles in `src/css/components/`:

```css
/* src/css/components/custom.css */
@layer components {
    .my-custom-component {
        @apply bg-white border border-gray-200 rounded-lg p-4 shadow-sm;
    }
    
    .my-custom-button {
        @apply px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 focus:ring-2 focus:ring-purple-500;
    }
}
```

Then import it in `src/css/main.css`:

```css
/* Add to src/css/main.css */
@import './components/custom.css';
```

### Adding Page-Specific Styles

Create page-specific styles in `src/css/pages/`:

```css
/* src/css/pages/dashboard.css */
@layer components {
    .dashboard-grid {
        @apply grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6;
    }
    
    .dashboard-card {
        @apply bg-white rounded-lg shadow p-6;
    }
}
```

### Customizing Tailwind Theme

Edit `tailwind.config.js` to customize colors, fonts, and other design tokens:

```javascript
module.exports = {
  theme: {
    extend: {
      colors: {
        'admin-primary': {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        'admin-secondary': {
          500: '#6b7280',
          600: '#4b5563',
        }
      },
      fontFamily: {
        'admin': ['Inter', 'sans-serif'],
      }
    },
  },
}
```

## 🔄 HTMX Integration

The build system automatically handles HTMX compatibility:

### Automatic Re-initialization

Flowbite components are automatically re-initialized when HTMX updates the DOM:

```javascript
// Automatically handled by flowbite-init.js
document.body.addEventListener('htmx:afterSwap', function() {
    initFlowbite(); // Re-initialize Flowbite components
});
```

### Using with HTMX Responses

```html
<!-- In your HTMX response templates -->
<div hx-get="/admin/users" hx-target="#user-list">
    <!-- Flowbite components work automatically after HTMX swap -->
    <button class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5">
        Load Users
    </button>
</div>

<div id="user-list">
    <!-- Flowbite components in HTMX responses work automatically -->
</div>
```

## 🎭 Alpine.js Integration

The system includes Alpine.js data components for common Flowbite patterns:

### Modal Component

```html
<div x-data="flowbiteModal()">
    <button @click="open()" class="btn-flowbite-primary">Open Modal</button>
    
    <div x-show="show" class="modal-backdrop" @click="close()">
        <div class="modal-content" @click.stop>
            <h3>Modal Title</h3>
            <button @click="close()">Close</button>
        </div>
    </div>
</div>
```

### Dropdown Component

```html
<div x-data="flowbiteDropdown()">
    <button @click="toggle()" class="btn-flowbite-secondary">
        Dropdown
    </button>
    
    <div x-show="open" @click.away="close()" class="dropdown-menu">
        <a href="#" @click="close()">Option 1</a>
        <a href="#" @click="close()">Option 2</a>
    </div>
</div>
```

### Toast Notifications

```html
<div x-data="flowbiteToast()" x-show="show" x-init="autoDismiss(3000)">
    <div class="toast-content">
        <span>Success message!</span>
        <button @click="dismiss()">×</button>
    </div>
</div>
```

## 🛠️ Development Tips

### File Watching

The watch mode automatically rebuilds when you change files:

```bash
# Start watching (runs in background)
npm run dev

# You'll see output like:
# 👀 Watching for changes...
# 📝 File changed: src/css/main.css
# 🔨 Rebuilding CSS...
# ✅ CSS rebuild completed
```

### Build Output

Check build output sizes and content:

```bash
# Check compiled CSS size
ls -lh dist/css/main.css

# Check compiled JS size  
ls -lh dist/js/bundle.js

# Preview compiled CSS (first 20 lines)
head -20 dist/css/main.css
```

### Debugging Styles

Use browser dev tools to inspect Tailwind classes:

1. Open browser dev tools
2. Inspect element
3. Look for Tailwind utility classes
4. Check if Flowbite components are initialized

## 🔍 Troubleshooting

### Common Issues

#### Build Fails
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
npm run build
```

#### Styles Not Updating
```bash
# Force rebuild CSS
npm run build:css

# Check if symlinks are working
ls -la ../sqladmin/statics/css/main.css
```

#### Flowbite Components Not Working
```bash
# Check if bundle.js is loaded in browser console
# Look for errors in browser dev tools
# Verify HTMX is re-initializing components
```

#### Watch Mode Not Working
```bash
# Kill existing processes
pkill -f "npm run"

# Restart watch mode
npm run dev
```

### File Permissions

The build system automatically copies files to the sqladmin/statics directory, so no symlink permissions are needed.

### Node.js Version Issues

Ensure you're using Node.js 16+:

```bash
node --version  # Should be 16.0.0 or higher
npm --version   # Should be 8.0.0 or higher
```

## 📚 Resources

- [Flowbite Documentation](https://flowbite.com/docs/getting-started/introduction/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [HTMX Documentation](https://htmx.org/docs/)
- [Alpine.js Documentation](https://alpinejs.dev/)
- [PostCSS Documentation](https://postcss.org/)

## 🤝 Contributing

When adding new UI components:

1. Add styles to appropriate `src/css/components/` file
2. Update `src/css/main.css` with imports if needed
3. Test with `npm run dev`
4. Build for production with `npm run build`
5. Verify symlinks are updated in `../sqladmin/statics/`

## 📄 License

This UI build system is part of SQLAdmin-HTMX and follows the same license terms.
