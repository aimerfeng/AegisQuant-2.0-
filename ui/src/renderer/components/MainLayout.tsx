/**
 * Titan-Quant Main Layout Component
 * 
 * This component integrates Golden-Layout for multi-window management.
 * Provides the main workspace with drag-and-drop panel support.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { WorkspaceLayout } from '../layouts';
import LanguageSelector from './LanguageSelector';
import LayoutToolbar from './LayoutToolbar';
import './MainLayout.css';

const MainLayout: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="main-layout">
      <div className="layout-toolbar">
        <div className="toolbar-left">
          <LayoutToolbar />
        </div>
        <div className="toolbar-right">
          <LanguageSelector />
        </div>
      </div>
      <div className="layout-workspace">
        <WorkspaceLayout />
      </div>
    </div>
  );
};

export default MainLayout;
