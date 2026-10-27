// OneASR Theme Manager (Dark / Light / Auto)
import { ref } from 'vue';

export const currentTheme = ref(localStorage.getItem('oneasr_theme') || 'auto');

let mediaQuery = null;
let mediaListener = null;

function handleSystemThemeChange(e) {
  if (currentTheme.value === 'auto') {
    document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
  }
}

export function initTheme() {
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  mediaListener = (e) => handleSystemThemeChange(e);
  if (mediaQuery.addEventListener) {
    mediaQuery.addEventListener('change', mediaListener);
  } else if (mediaQuery.addListener) {
    mediaQuery.addListener(mediaListener);
  }

  setTheme(currentTheme.value);
}

export function setTheme(theme) {
  currentTheme.value = theme;
  localStorage.setItem('oneasr_theme', theme);

  if (theme === 'auto') {
    const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  } else {
    document.documentElement.setAttribute('data-theme', theme);
  }
}
