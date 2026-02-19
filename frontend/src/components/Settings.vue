<template>
  <el-card class="section-card">
    <template #header>
      <div class="card-header">
        <span class="card-header-icon">⚙️</span>
        <span>Настройки</span>
      </div>
    </template>

    <div v-if="loading">
      <el-skeleton :rows="4" animated />
    </div>

    <el-form
      v-else
      :model="form"
      label-position="top"
      @submit.prevent="saveSettings"
    >
      <el-form-item label="Часовой пояс">
        <el-input
          v-model="form.timezone"
          placeholder="Europe/Moscow"
          clearable
        >
          <template #prefix>
            <el-icon><Clock /></el-icon>
          </template>
        </el-input>
      </el-form-item>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="Утро (HH:MM)">
            <el-input
              v-model="form.morning_time"
              placeholder="07:00"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="Вечер (HH:MM)">
            <el-input
              v-model="form.evening_time"
              placeholder="21:00"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="Интервал повторов (мин)">
            <el-input-number
              v-model="form.reminder_interval_minutes"
              :min="5"
              :max="720"
              controls-position="right"
              style="width: 100%;"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="Макс. повторов">
            <el-input-number
              v-model="form.reminder_max_attempts"
              :min="0"
              :max="10"
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
        💾 Сохранить настройки
      </el-button>
    </el-form>
  </el-card>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock } from '@element-plus/icons-vue'
import { useApi } from '@/composables/useApi'

const props = defineProps({
  settings: {
    type: Object,
    default: () => ({}),
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['saved'])

const { api } = useApi()
const saving = ref(false)

const form = reactive({
  timezone: '',
  morning_time: '',
  evening_time: '',
  reminder_interval_minutes: 60,
  reminder_max_attempts: 1,
})

watch(
  () => props.settings,
  (s) => {
    if (s) {
      form.timezone = s.timezone || ''
      form.morning_time = s.morning_time || ''
      form.evening_time = s.evening_time || ''
      form.reminder_interval_minutes = s.reminder_interval_minutes ?? 60
      form.reminder_max_attempts = s.reminder_max_attempts ?? 1
    }
  },
  { immediate: true }
)

async function saveSettings() {
  saving.value = true
  try {
    await api.put('/api/settings', {
      timezone: form.timezone?.trim() || null,
      morning_time: form.morning_time?.trim() || null,
      evening_time: form.evening_time?.trim() || null,
      reminder_interval_minutes: form.reminder_interval_minutes || null,
      reminder_max_attempts: form.reminder_max_attempts ?? null,
    })
    ElMessage.success('Настройки сохранены')
    emit('saved')
  } catch (err) {
    ElMessage.error('Ошибка: ' + err.message)
  } finally {
    saving.value = false
  }
}
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
}
</style>
