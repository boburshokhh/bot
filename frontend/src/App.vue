<template>
  <el-config-provider :locale="ruLocale" :dark="isDark">
    <div class="app-container">
      <div class="container">
        <TodayPlan
          :tasks="today.tasks"
          :plan-date="today.date"
          :loading="loading.today"
          @refresh="loadToday"
        />

        <CreatePlan @saved="handlePlanSaved" />

        <Settings
          :settings="settings"
          :loading="loading.settings"
          @saved="loadSettings"
        />

        <Stats :stats="stats" :loading="loading.stats" />

        <History />
      </div>
    </div>
  </el-config-provider>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import ru from 'element-plus/es/locale/lang/ru'
import { useTelegramTheme } from '@/composables/useTelegramTheme'
import { useWebApp } from '@/composables/useWebApp'
import { useApi } from '@/composables/useApi'
import TodayPlan from '@/components/TodayPlan.vue'
import CreatePlan from '@/components/CreatePlan.vue'
import Settings from '@/components/Settings.vue'
import Stats from '@/components/Stats.vue'
import History from '@/components/History.vue'

const ruLocale = ru

const { init: initWebApp } = useWebApp()
const { isDark } = useTelegramTheme()
const { api } = useApi()

const loading = reactive({
  today: true,
  settings: true,
  stats: true,
})

const today = ref({ tasks: [], date: null, exists: false })
const settings = ref({})
const stats = ref({ total_plans: 0, avg_percent: 0, current_streak: 0 })

async function loadToday() {
  loading.today = true
  try {
    const data = await api.get('/api/today')
    today.value = data
  } catch (err) {
    ElMessage.error('Ошибка загрузки плана: ' + err.message)
  } finally {
    loading.today = false
  }
}

async function loadSettings() {
  loading.settings = true
  try {
    const s = await api.get('/api/settings')
    settings.value = s
  } catch (err) {
    ElMessage.error('Ошибка загрузки настроек: ' + err.message)
  } finally {
    loading.settings = false
  }
}

async function loadStats() {
  loading.stats = true
  try {
    const s = await api.get('/api/stats')
    stats.value = s
  } catch (err) {
    ElMessage.error('Ошибка загрузки статистики: ' + err.message)
  } finally {
    loading.stats = false
  }
}

async function handlePlanSaved() {
  await Promise.all([loadToday(), loadStats()])
}

onMounted(async () => {
  initWebApp()
  await Promise.all([loadToday(), loadSettings(), loadStats()])
  ElMessage.success({ message: 'WebApp готов', duration: 2000 })
})
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  padding: 16px;
}

.container {
  max-width: 600px;
  margin: 0 auto;
}
</style>
