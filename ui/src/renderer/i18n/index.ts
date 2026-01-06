/**
 * Titan-Quant I18N Configuration
 * 
 * Integrates react-i18next with backend language packs.
 * Supports dynamic language switching and parameter interpolation.
 * 
 * Requirements: I18N Support
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// Import language resources
// These will be loaded from backend language packs
import en from './locales/en.json';
import zh_cn from './locales/zh_cn.json';
import zh_tw from './locales/zh_tw.json';

// Define supported languages
export const supportedLanguages = ['en', 'zh_cn', 'zh_tw'] as const;
export type SupportedLanguage = typeof supportedLanguages[number];

// Language display names
export const languageNames: Record<SupportedLanguage, string> = {
  en: 'English',
  zh_cn: '简体中文',
  zh_tw: '繁體中文',
};

// Initialize i18next
i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      zh_cn: { translation: zh_cn },
      zh_tw: { translation: zh_tw },
    },
    lng: 'zh_cn', // Default language
    fallbackLng: 'en',
    
    interpolation: {
      escapeValue: false, // React already escapes values
      // Use {variable} format to match backend language packs
      prefix: '{',
      suffix: '}',
    },

    // Debug mode in development
    debug: process.env.NODE_ENV === 'development',

    // React specific options
    react: {
      useSuspense: false,
    },
  });

/**
 * Change the current language
 */
export const changeLanguage = (lang: SupportedLanguage): Promise<void> => {
  return i18n.changeLanguage(lang).then(() => {
    // Store preference in localStorage
    localStorage.setItem('titan-quant-language', lang);
  });
};

/**
 * Get the current language
 */
export const getCurrentLanguage = (): SupportedLanguage => {
  return i18n.language as SupportedLanguage;
};

/**
 * Load language from localStorage on startup
 */
export const loadStoredLanguage = (): void => {
  const stored = localStorage.getItem('titan-quant-language');
  if (stored && supportedLanguages.includes(stored as SupportedLanguage)) {
    i18n.changeLanguage(stored);
  }
};

// Load stored language preference
loadStoredLanguage();

export default i18n;
