/**
 * Titan-Quant I18N Store
 * 
 * Zustand store for managing internationalization state.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import i18n from 'i18next';

export type SupportedLanguage = 'en' | 'zh_cn' | 'zh_tw';

interface I18nStore {
  currentLanguage: SupportedLanguage;
  availableLanguages: SupportedLanguage[];
  
  // Actions
  setLanguage: (lang: SupportedLanguage) => void;
  toggleLanguage: () => void;
}

export const useI18nStore = create<I18nStore>()(
  persist(
    (set, get) => ({
      currentLanguage: 'zh_cn',
      availableLanguages: ['en', 'zh_cn', 'zh_tw'],

      setLanguage: (lang: SupportedLanguage) => {
        i18n.changeLanguage(lang);
        set({ currentLanguage: lang });
      },

      toggleLanguage: () => {
        const { currentLanguage, availableLanguages } = get();
        const currentIndex = availableLanguages.indexOf(currentLanguage);
        const nextIndex = (currentIndex + 1) % availableLanguages.length;
        const nextLang = availableLanguages[nextIndex];
        
        i18n.changeLanguage(nextLang);
        set({ currentLanguage: nextLang });
      },
    }),
    {
      name: 'titan-quant-i18n',
      partialize: (state) => ({ currentLanguage: state.currentLanguage }),
    }
  )
);
