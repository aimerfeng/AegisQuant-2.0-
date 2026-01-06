# Titan-Quant UI

Electron + React frontend for the Titan-Quant quantitative trading backtest system.

## Tech Stack

- **Electron**: Desktop application framework
- **React 18**: UI library
- **TypeScript**: Type-safe JavaScript
- **Webpack**: Module bundler
- **Zustand**: State management
- **react-i18next**: Internationalization
- **Golden-Layout**: Multi-window layout management
- **Monaco Editor**: Code editor (Python strategy editing)
- **Lightweight-charts**: K-line chart visualization

## Project Structure

```
ui/
├── src/
│   ├── main/                 # Electron main process
│   │   └── main.ts
│   └── renderer/             # React renderer process
│       ├── components/       # React components
│       ├── services/         # Services (WebSocket, etc.)
│       ├── stores/           # Zustand stores
│       ├── types/            # TypeScript type definitions
│       ├── i18n/             # Internationalization
│       │   └── locales/      # Language files
│       ├── styles/           # CSS styles
│       ├── App.tsx           # Main App component
│       └── index.tsx         # Entry point
├── dist/                     # Build output
├── package.json
├── tsconfig.json
├── webpack.main.config.js    # Webpack config for main process
├── webpack.renderer.config.js # Webpack config for renderer
└── README.md
```

## Development

### Prerequisites

- Node.js 18+
- npm or yarn

### Install Dependencies

```bash
cd ui
npm install
```

### Development Mode

```bash
npm run dev
```

This starts both the Webpack dev server (renderer) and watches the main process.

### Build

```bash
npm run build
```

### Package for Distribution

```bash
npm run dist
```

## Features

- **WebSocket Communication**: Real-time connection to backend Core Engine
- **Multi-language Support**: English, Simplified Chinese, Traditional Chinese
- **Dark Theme**: Professional trading interface
- **Responsive Layout**: Golden-Layout based multi-window management

## Configuration

The UI connects to the backend WebSocket server at `ws://localhost:8765` by default.
This can be configured in the connection store.
