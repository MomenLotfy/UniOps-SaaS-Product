import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { I18N } from '../i18n/translations';

interface LandingContextValue {
  theme: string;
  toggleTheme: () => void;
  lang: string;
  setLang: (l: string) => void;
  t: (key: string) => string;
}

const LandingContext = createContext<LandingContextValue | null>(null);

export function LandingProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<string>(() => localStorage.getItem('uniops_theme') || 'dark');
  const [lang, setLangState] = useState<string>(() => localStorage.getItem('uniops_lang') || 'en');

  useEffect(() => {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('uniops_theme', theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    localStorage.setItem('uniops_lang', lang);
    return () => {
      document.documentElement.lang = 'en';
      document.documentElement.dir = 'ltr';
    };
  }, [lang]);

  const toggleTheme = () => setThemeState(t => (t === 'dark' ? 'light' : 'dark'));
  const setLang = (l: string) => setLangState(l);
  const t = (key: string) => I18N[lang]?.[key] ?? I18N.en[key] ?? key;

  return (
    <LandingContext.Provider value={{ theme, toggleTheme, lang, setLang, t }}>
      {children}
    </LandingContext.Provider>
  );
}

export function useLanding(): LandingContextValue {
  const ctx = useContext(LandingContext);
  if (!ctx) throw new Error('useLanding must be used within LandingProvider');
  return ctx;
}
