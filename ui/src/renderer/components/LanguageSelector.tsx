/**
 * Titan-Quant Language Selector Component
 * 
 * Allows users to switch between supported languages.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { useI18nStore, SupportedLanguage } from '../stores/i18nStore';
import { languageNames } from '../i18n/index';
import './LanguageSelector.css';

const LanguageSelector: React.FC = () => {
  const { i18n } = useTranslation();
  const { currentLanguage, availableLanguages, setLanguage } = useI18nStore();

  const handleLanguageChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const newLang = event.target.value as SupportedLanguage;
    setLanguage(newLang);
  };

  return (
    <div className="language-selector">
      <select
        value={currentLanguage}
        onChange={handleLanguageChange}
        className="language-select"
      >
        {availableLanguages.map((lang) => (
          <option key={lang} value={lang}>
            {languageNames[lang] || lang}
          </option>
        ))}
      </select>
    </div>
  );
};

export default LanguageSelector;
