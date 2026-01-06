/**
 * Titan-Quant Renderer Entry Point
 * 
 * This is the main entry point for the React application
 * running in the Electron renderer process.
 */

import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles/global.css';
import './i18n/index';

const container = document.getElementById('root');
if (!container) {
  throw new Error('Root element not found');
}

const root = createRoot(container);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
