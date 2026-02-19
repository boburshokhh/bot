import { ref, readonly } from 'vue'

const tg = window.Telegram?.WebApp || null

export function useWebApp() {
  const isReady = ref(false)

  function init() {
    if (tg) {
      tg.ready()
      tg.expand()
      isReady.value = true
    }
  }

  function getInitData() {
    if (tg?.initData) return tg.initData
    const p = new URLSearchParams(window.location.search)
    return p.get('initData') || ''
  }

  function getColorScheme() {
    return tg?.colorScheme || 'light'
  }

  function onThemeChanged(callback) {
    if (tg) {
      tg.onEvent('themeChanged', callback)
    }
  }

  function offThemeChanged(callback) {
    if (tg) {
      tg.offEvent('themeChanged', callback)
    }
  }

  return {
    tg: readonly(ref(tg)),
    isReady: readonly(isReady),
    init,
    getInitData,
    getColorScheme,
    onThemeChanged,
    offThemeChanged,
  }
}
