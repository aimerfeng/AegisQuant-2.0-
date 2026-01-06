/**
 * Placeholder Panel Component
 * 
 * A generic placeholder panel used for components that are not yet implemented.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { PanelComponentProps } from '../../types/layout';
import './PlaceholderPanel.css';

interface PlaceholderPanelProps extends PanelComponentProps {
  panelName: string;
  icon?: string;
}

const PlaceholderPanel: React.FC<PlaceholderPanelProps> = ({ 
  panelName, 
  icon = '📊',
  componentState 
}) => {
  const { t } = useTranslation();

  return (
    <div className="placeholder-panel">
      <div className="placeholder-content">
        <span className="placeholder-icon">{icon}</span>
        <h3 className="placeholder-title">{panelName}</h3>
        <p className="placeholder-description">
          {t('layout.componentPlaceholder', { name: panelName })}
        </p>
        {componentState && Object.keys(componentState).length > 0 && (
          <div className="placeholder-state">
            <code>{JSON.stringify(componentState, null, 2)}</code>
          </div>
        )}
      </div>
    </div>
  );
};

export default PlaceholderPanel;
