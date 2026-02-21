<template>
  <el-card class="section-card">
    <template #header>
      <div class="card-header">
        <el-icon class="card-header-icon"><Bell /></el-icon>
        <span>Напоминания</span>
      </div>
    </template>

    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <template v-else>
      <el-row v-if="stats.total >= 0" :gutter="12" class="stats-row">
        <el-col :xs="12" :sm="6">
          <div class="stat-item">
            <el-statistic :value="stats.total" title="Всего" />
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-item stat-enabled">
            <el-statistic :value="stats.enabled" title="Активных" />
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-item stat-done">
            <el-statistic :value="stats.done_today" title="Выполнено сегодня" />
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-item stat-sent">
            <el-statistic :value="stats.sent_today" title="Отправлено сегодня" />
          </div>
        </el-col>
      </el-row>

      <el-empty
        v-if="!reminders.length"
        description="Нет напоминаний"
        :image-size="80"
      >
        <template #image>
          <el-icon class="empty-icon"><BellFilled /></el-icon>
        </template>
      </el-empty>

      <div v-else class="reminders-list">
        <div
          v-for="r in reminders"
          :key="r.id"
          class="reminder-item"
          :class="{ disabled: !r.enabled }"
        >
          <div class="reminder-main">
            <span class="reminder-time">{{ r.time_of_day }}</span>
            <span class="reminder-desc">{{ r.description }}</span>
            <el-text type="info" size="small" class="reminder-meta">
              {{ r.day_of_month ? `Каждое ${r.day_of_month} число` : 'Ежедневно' }} | Повтор: каждые {{ r.repeat_interval_minutes }} мин, до {{ r.max_attempts_per_day }} раз в день
            </el-text>
            <el-tag v-if="r.done_today" type="success" size="small">Выполнено сегодня</el-tag>
            <el-tag v-else-if="!r.enabled" type="info" size="small">Отключено</el-tag>
          </div>
          <div class="reminder-actions">
            <el-button
              type="primary"
              size="small"
              circle
              title="Изменить"
              @click="openEdit(r)"
            >
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button
              v-if="r.enabled && !r.done_today"
              type="success"
              size="small"
              circle
              title="Выполнено сегодня"
              @click="markDone(r.id)"
            >
              <el-icon><Check /></el-icon>
            </el-button>
            <el-button
              :type="r.enabled ? 'warning' : 'primary'"
              size="small"
              circle
              :title="r.enabled ? 'Отключить' : 'Включить'"
              @click="toggle(r.id, !r.enabled)"
            >
              <el-icon><component :is="r.enabled ? 'CircleClose' : 'Bell'" /></el-icon>
            </el-button>
            <el-button
              type="danger"
              size="small"
              circle
              title="Удалить"
              @click="confirmDelete(r)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <el-divider />

      <div class="add-section">
        <el-text tag="b" class="add-title">Добавить напоминание</el-text>
        <el-form
          :model="form"
          label-position="top"
          @submit.prevent="addReminder"
        >
          <el-row :gutter="12">
            <el-col :span="24">
              <el-form-item label="Частота">
                <el-radio-group v-model="form.is_monthly" size="small">
                  <el-radio-button :label="false">Ежедневно</el-radio-button>
                  <el-radio-button :label="true">Раз в месяц</el-radio-button>
                </el-radio-group>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="8">
              <el-form-item label="Время (HH:MM)">
                <el-input
                  v-model="form.time_of_day"
                  placeholder="14:30"
                  maxlength="5"
                />
              </el-form-item>
            </el-col>
            <el-col :span="6" v-if="form.is_monthly">
              <el-form-item label="Число">
                <el-input-number
                  v-model="form.day_of_month"
                  :min="1"
                  :max="31"
                  controls-position="right"
                  style="width: 100%;"
                />
              </el-form-item>
            </el-col>
            <el-col :span="form.is_monthly ? 10 : 16">
              <el-form-item label="Описание">
                <el-input
                  v-model="form.description"
                  placeholder="Например: Выпить таблетку"
                  clearable
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="Повторять каждые (мин)">
                <el-input-number
                  v-model="form.repeat_interval_minutes"
                  :min="1"
                  :max="1440"
                  controls-position="right"
                  style="width: 100%;"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Макс. раз в день">
                <el-input-number
                  v-model="form.max_attempts_per_day"
                  :min="1"
                  :max="50"
                  controls-position="right"
                  style="width: 100%;"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-button
            type="primary"
            native-type="submit"
            :loading="saving"
            style="width: 100%;"
          >
            <el-icon><Plus /></el-icon>
            <span>Добавить</span>
          </el-button>
        </el-form>
      </div>
    </template>

    <el-dialog
      v-model="editDialogVisible"
      title="Изменить напоминание"
      width="90%"
      :close-on-click-modal="false"
    >
      <el-form :model="editForm" label-position="top">
        <el-row :gutter="12">
          <el-col :span="24">
            <el-form-item label="Частота">
              <el-radio-group v-model="editForm.is_monthly" size="small">
                <el-radio-button :label="false">Ежедневно</el-radio-button>
                <el-radio-button :label="true">Раз в месяц</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="Время (HH:MM)">
              <el-input v-model="editForm.time_of_day" placeholder="14:30" maxlength="5" />
            </el-form-item>
          </el-col>
          <el-col :span="6" v-if="editForm.is_monthly">
            <el-form-item label="Число">
              <el-input-number
                v-model="editForm.day_of_month"
                :min="1"
                :max="31"
                controls-position="right"
                style="width: 100%;"
              />
            </el-form-item>
          </el-col>
          <el-col :span="editForm.is_monthly ? 10 : 16">
            <el-form-item label="Описание">
              <el-input v-model="editForm.description" placeholder="Описание" clearable />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="Повторять каждые (мин)">
              <el-input-number
                v-model="editForm.repeat_interval_minutes"
                :min="1"
                :max="1440"
                controls-position="right"
                style="width: 100%;"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Макс. раз в день">
              <el-input-number
                v-model="editForm.max_attempts_per_day"
                :min="1"
                :max="50"
                controls-position="right"
                style="width: 100%;"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">Отмена</el-button>
        <el-button type="primary" :loading="savingEdit" @click="saveEdit">
          Сохранить
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="deleteDialogVisible"
      title="Удалить напоминание?"
      width="90%"
      :close-on-click-modal="true"
    >
      <span>Напоминание «{{ reminderToDelete?.description }}» будет удалено.</span>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">Отмена</el-button>
        <el-button type="danger" :loading="deleting" @click="doDelete">
          Удалить
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Bell,
  BellFilled,
  Check,
  Delete,
  Edit,
  Plus,
  CircleClose,
} from '@element-plus/icons-vue'
import { useApi } from '@/composables/useApi'

const emit = defineEmits(['refresh'])

const { api } = useApi()
const reminders = ref([])
const stats = ref({
  total: -1,
  enabled: 0,
  disabled: 0,
  done_today: 0,
  sent_today: 0,
})
const loading = ref(true)
const saving = ref(false)
const deleting = ref(false)
const deleteDialogVisible = ref(false)
const reminderToDelete = ref(null)

const editDialogVisible = ref(false)
const savingEdit = ref(false)
const editingReminderId = ref(null)
const editForm = reactive({
  time_of_day: '09:00',
  description: '',
  repeat_interval_minutes: 30,
  max_attempts_per_day: 3,
  is_monthly: false,
  day_of_month: 1,
})

const form = reactive({
  time_of_day: '09:00',
  description: '',
  repeat_interval_minutes: 30,
  max_attempts_per_day: 3,
  is_monthly: false,
  day_of_month: 1,
})

function validateTime(s) {
  return /^\d{2}:\d{2}$/.test(s) && parseInt(s.slice(0, 2), 10) <= 23 && parseInt(s.slice(3, 5), 10) <= 59
}

async function loadReminders() {
  loading.value = true
  try {
    const [listData, statsData] = await Promise.all([
      api.get('/api/reminders'),
      api.get('/api/reminders/stats'),
    ])
    reminders.value = listData
    stats.value = { ...stats.value, ...statsData }
  } catch (err) {
    ElMessage.error('Ошибка загрузки: ' + err.message)
  } finally {
    loading.value = false
  }
}

async function addReminder() {
  const desc = form.description?.trim()
  if (!desc) {
    ElMessage.warning('Введите описание')
    return
  }
  if (!validateTime(form.time_of_day)) {
    ElMessage.warning('Время в формате HH:MM (например 14:30)')
    return
  }
  saving.value = true
  try {
    await api.post('/api/reminders', {
      time_of_day: form.time_of_day,
      description: desc,
      repeat_interval_minutes: form.repeat_interval_minutes,
      max_attempts_per_day: form.max_attempts_per_day,
      day_of_month: form.is_monthly ? form.day_of_month : null,
    })
    ElMessage.success('Напоминание добавлено')
    form.description = ''
    await loadReminders()
    emit('refresh')
  } catch (err) {
    ElMessage.error('Ошибка: ' + err.message)
  } finally {
    saving.value = false
  }
}

async function toggle(id, enabled) {
  try {
    await api.put(`/api/reminders/${id}`, { enabled })
    ElMessage.success(enabled ? 'Напоминание включено' : 'Напоминание отключено')
    await loadReminders()
    emit('refresh')
  } catch (err) {
    ElMessage.error('Ошибка: ' + err.message)
  }
}

async function markDone(id) {
  try {
    await api.put(`/api/reminders/${id}`, { mark_done_today: true })
    ElMessage.success('Отмечено как выполненное на сегодня')
    await loadReminders()
    emit('refresh')
  } catch (err) {
    ElMessage.error('Ошибка: ' + err.message)
  }
}

function openEdit(r) {
  editingReminderId.value = r.id
  editForm.time_of_day = r.time_of_day
  editForm.description = r.description
  editForm.repeat_interval_minutes = r.repeat_interval_minutes
  editForm.max_attempts_per_day = r.max_attempts_per_day
  editForm.is_monthly = r.day_of_month != null
  editForm.day_of_month = r.day_of_month || 1
  editDialogVisible.value = true
}

async function saveEdit() {
  const desc = editForm.description?.trim()
  if (!desc) {
    ElMessage.warning('Введите описание')
    return
  }
  if (!validateTime(editForm.time_of_day)) {
    ElMessage.warning('Время в формате HH:MM (например 14:30)')
    return
  }
  const id = editingReminderId.value
  if (id == null) return
  savingEdit.value = true
  try {
    await api.put(`/api/reminders/${id}`, {
      time_of_day: editForm.time_of_day,
      description: desc,
      repeat_interval_minutes: editForm.repeat_interval_minutes,
      max_attempts_per_day: editForm.max_attempts_per_day,
      day_of_month: editForm.is_monthly ? editForm.day_of_month : null,
    })
    ElMessage.success('Напоминание обновлено')
    editDialogVisible.value = false
    await loadReminders()
    emit('refresh')
  } catch (err) {
    ElMessage.error('Ошибка: ' + err.message)
  } finally {
    savingEdit.value = false
  }
}

function confirmDelete(r) {
  reminderToDelete.value = r
  deleteDialogVisible.value = true
}

async function doDelete() {
  if (!reminderToDelete.value) return
  deleting.value = true
  try {
    await api.delete(`/api/reminders/${reminderToDelete.value.id}`)
    ElMessage.success('Напоминание удалено')
    deleteDialogVisible.value = false
    reminderToDelete.value = null
    await loadReminders()
    emit('refresh')
  } catch (err) {
    ElMessage.error('Ошибка: ' + err.message)
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  loadReminders()
})

defineExpose({ loadReminders })
</script>

<style scoped>
.section-card {
  margin-bottom: 16px;
  border-radius: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
}

.card-header-icon {
  font-size: 20px;
  color: var(--el-color-primary);
}

.loading-container {
  padding: 8px 0;
}

.empty-icon {
  font-size: 48px;
  color: var(--el-text-color-placeholder);
}

.reminders-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.reminder-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  background: var(--el-fill-color-light);
}

.reminder-item.disabled {
  opacity: 0.7;
}

.reminder-main {
  flex: 1;
  min-width: 0;
}

.reminder-time {
  font-weight: 600;
  font-size: 16px;
  margin-right: 8px;
  color: var(--el-text-color-primary);
}

.reminder-desc {
  color: var(--el-text-color-regular);
}

.reminder-meta {
  display: block;
  margin-top: 4px;
}

.reminder-main .el-tag {
  margin-top: 6px;
}

.reminder-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.add-section {
  margin-top: 8px;
}

.add-title {
  display: block;
  margin-bottom: 12px;
  font-size: 14px;
}

.stats-row {
  margin-bottom: 16px;
  text-align: center;
}

.stat-item {
  padding: 12px 8px;
  background: var(--el-fill-color-light);
  border-radius: 12px;
}

.stat-enabled {
  background: var(--el-color-primary-light-9);
}

.stat-done {
  background: var(--el-color-success-light-9);
}

.stat-sent {
  background: var(--el-color-info-light-9);
}

@media (max-width: 768px) {
  .reminder-item {
    flex-direction: column;
    align-items: stretch;
  }

  .reminder-actions {
    justify-content: flex-end;
  }

  .stats-row .el-col {
    margin-bottom: 8px;
  }
}
</style>
