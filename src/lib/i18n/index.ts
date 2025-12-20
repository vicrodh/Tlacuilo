/**
 * i18n utilities for Tlacuilo.
 * Provides type-safe translation access.
 */

import { getSettings, type Language } from '$lib/stores/settings.svelte';
import translations, { type Translations } from './translations';

/**
 * Get translations for the current language.
 * Returns the full translations object for the active language.
 */
export function useTranslations(): Translations {
  const settings = getSettings();
  return translations[settings.language] || translations.en;
}

/**
 * Get a specific translation by path.
 * @param path - Dot-separated path to the translation key
 * @example t('nav.home') => 'Home'
 */
export function t(path: string): string {
  const settings = getSettings();
  const lang = settings.language || 'en';
  const trans = translations[lang] || translations.en;

  const keys = path.split('.');
  let value: any = trans;

  for (const key of keys) {
    if (value && typeof value === 'object' && key in value) {
      value = value[key];
    } else {
      // Fallback to English if key not found
      value = getNestedValue(translations.en, keys);
      break;
    }
  }

  return typeof value === 'string' ? value : path;
}

/**
 * Helper to get nested value from object.
 */
function getNestedValue(obj: any, keys: string[]): any {
  let value = obj;
  for (const key of keys) {
    if (value && typeof value === 'object' && key in value) {
      value = value[key];
    } else {
      return undefined;
    }
  }
  return value;
}

/**
 * Get translations for a specific language.
 */
export function getTranslationsForLanguage(lang: Language): Translations {
  return translations[lang] || translations.en;
}

export { translations };
export type { Translations };
