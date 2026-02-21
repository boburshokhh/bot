<template>
  <el-config-provider :locale="ruLocale" :dark="isDark">
    <div class="app-container">
      <div class="container">
        <el-card class="header-card" shadow="never">
          <div class="app-header">
            <div class="app-title">
              <el-icon class="app-icon"><Calendar /></el-icon>
              <span>Planning Bot</span>
            </div>
          </div>
        </el-card>

        <div v-if="hasAccessError" style="margin-top: 20px; text-align: center;">
          <el-result
            icon="warning"
            title="Доступ ограничен"
            sub-title="Пожалуйста, вернитесь в бот и завершите первоначальную настройку (выбор часового пояса и времени уведомлений)."
          >
          </el-result>
        </div>

        <el-tabs v-else v-model="activeTab" class="main-tabs" @tab-change="handleTabChange">
          <el-tab-pane label="План" name="plan">
            <template #label>
              <span class="tab-label">
                <el-icon><Document /></el-icon>
                <span>План</span>
              </span>
            </template>
            <TodayPlan
              :tasks="today.tasks"
              :plan-date="today.date"
              :loading="loading.today"
              @refresh="loadToday"
            />
            <CreatePlan @saved="handlePlanSaved" />
          </el-tab-pane>

          <el-tab-pane label="Напоминания" name="reminders">
            <template #label>
              <span class="tab-label">
                <el-icon><Bell /></el-icon>
                <span>Напоминания</span>
              </span>
            </template>
            <Reminders @refresh="() => {}" />
          </el-tab-pane>

          <el-tab-pane label="Статистика" name="stats">
            <template #label>
              <span class="tab-label">
                <el-icon><DataAnalysis /></el-icon>
                <span>Статистика</span>
              </span>
            </template>
            <Stats :stats="stats" :loading="loading.stats" />
            <History />
          </el-tab-pane>

          <el-tab-pane label="Настройки" name="settings">
            <template #label>
              <span class="tab-label">
                <el-icon><Setting /></el-icon>
                <span>Настройки</span>
              </span>
            </template>
            <Settings
              :settings="settings"
              :loading="loading.settings"
              @saved="loadSettings"
            />
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </el-config-provider>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Calendar, Document, DataAnalysis, Setting, Bell } from '@element-plus/icons-vue'
import ru from 'element-plus/es/locale/lang/ru'
import { useTelegramTheme } from '@/composables/useTelegramTheme'
import { useWebApp } from '@/composables/useWebApp'
import { useApi } from '@/composables/useApi'
import TodayPlan from '@/components/TodayPlan.vue'
import CreatePlan from '@/components/CreatePlan.vue'
import Settings from '@/components/Settings.vue'
import Stats from '@/components/Stats.vue'
import History from '@/components/History.vue'
import Reminders from '@/components/Reminders.vue'

const ruLocale = ru

const { init: initWebApp } = useWebApp()
const { isDark } = useTelegramTheme()
const { api } = useApi()

const activeTab = ref('plan')
const hasAccessError = ref(false)

const loading = reactive({
  today: true,
  settings: true,
  stats: true,
})

const today = ref({ tasks: [], date: null, exists: false })
const settings = ref({})
const stats = ref({ total_plans: 0, avg_percent: 0, current_streak: 0 })

function handleTabChange(name) {
  // Можно добавить логику при смене таба
}

function handleApiError(err) {
  if (err.message && err.message.includes('403')) {
    hasAccessError.value = true
    ElMessage.warning({ message: err.message || 'Пожалуйста, завершите настройку в боте', duration: 5000 })
  } else {
    ElMessage.error(err.message)
  }
}

async function loadToday() {
  if (hasAccessError.value) return
  loading.today = true
  try {
    const data = await api.get('/api/today')
    today.value = data
  } catch (err) {
    handleApiError(err)
  } finally {
    loading.today = false
  }
}

async function loadSettings() {
  if (hasAccessError.value) return
  loading.settings = true
  try {
    const s = await api.get('/api/settings')
    settings.value = s
  } catch (err) {
    handleApiError(err)
  } finally {
    loading.settings = false
  }
}

async function loadStats() {
  if (hasAccessError.value) return
  loading.stats = true
  try {
    const s = await api.get('/api/stats')
    stats.value = s
  } catch (err) {
    handleApiError(err)
  } finally {
    loading.stats = false
  }
}

async function handlePlanSaved() {
  await Promise.all([loadToday(), loadStats()])
}

onMounted(async () => {
  initWebApp()
  
  // Пытаемся загрузить настройки, чтобы сразу поймать 403, если он есть
  loading.today = true
  loading.settings = true
  loading.stats = true
  try {
    const s = await api.get('/api/settings')
    settings.value = s
    // Если 403 не было, грузим остальное
    await Promise.all([loadToday(), loadStats()])
    ElMessage.success({ message: 'WebApp готов', duration: 2000 })
  } catch (err) {
    handleApiError(err)
  } finally {
    loading.today = false
    loading.settings = false
    loading.stats = false
  }
})
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  padding: 12px;
  background: var(--el-bg-color-page);
}

.container {
  max-width: 600px;
  margin: 0 auto;
}

.header-card {
  margin-bottom: 12px;
  border-radius: 12px;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.app-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.app-icon {
  font-size: 24px;
  color: var(--el-color-primary);
}

.main-tabs {
  margin-top: 8px;
}

.main-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
  background: var(--el-bg-color);
  border-radius: 12px;
  padding: 4px;
}

.main-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0 8px;
}

.main-tabs :deep(.el-tabs__item) {
  padding: 12px 16px;
  border-radius: 8px;
  transition: all 0.3s;
}

.main-tabs :deep(.el-tabs__item.is-active) {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab-label .el-icon {
  font-size: 16px;
}

/* Адаптивность для мобильных */
@media (max-width: 768px) {
  .app-container {
    padding: 8px;
  }

  .app-title {
    font-size: 16px;
  }

  .main-tabs :deep(.el-tabs__item) {
    padding: 10px 12px;
    font-size: 14px;
  }

  .tab-label span {
    display: none;
  }

  .tab-label .el-icon {
    font-size: 18px;
  }
}

@media (max-width: 480px) {
  .container {
    max-width: 100%;
  }
}
</style>
