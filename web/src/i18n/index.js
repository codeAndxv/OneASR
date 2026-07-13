import { createI18n } from 'vue-i18n'
import zh from './zh'
import en from './en'

function getDefaultLocale() {
  const stored = localStorage.getItem('ui_locale')
  if (stored) return stored
  return navigator.language.startsWith('zh') ? 'zh' : 'en'
}

const i18n = createI18n({
  legacy: false,
  locale: getDefaultLocale(),
  fallbackLocale: 'en',
  messages: { zh, en },
})

export function setLocale(locale) {
  i18n.global.locale.value = locale
  localStorage.setItem('ui_locale', locale)
}

export function getLocale() {
  return i18n.global.locale.value
}

export default i18n
