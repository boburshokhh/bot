import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWebApp } from './useWebApp'

export function useTelegramTheme() {
  const { getColorScheme, onThemeChanged, offThemeChanged } = useWebApp()

  const colorScheme = ref(getColorScheme())
  const isDark = computed(() => colorScheme.value === 'dark')

  function applyTheme(scheme) {
    const html = document.documentElement
    if (scheme === 'dark') {
      html.classList.add('dark')
    } else {
      html.classList.remove('dark')
    }
  }

  function handleThemeChange() {
    colorScheme.value = getColorScheme()
    applyTheme(colorScheme.value)
  }

  onMounted(() => {
    applyTheme(colorScheme.value)
    onThemeChanged(handleThemeChange)
  })

  onUnmounted(() => {
    offThemeChanged(handleThemeChange)
  })

  return {
    colorScheme,
    isDark,
  }
}
