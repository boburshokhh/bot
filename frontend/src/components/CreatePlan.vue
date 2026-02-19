<template>
  <el-card class="section-card">
    <template #header>
      <div class="card-header">
        <el-icon class="card-header-icon"><EditPen /></el-icon>
        <span>Создать план на сегодня</span>
      </div>
    </template>

    <el-form @submit.prevent="savePlan">
      <el-form-item>
        <el-input
          v-model="planText"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 12 }"
          placeholder="Каждая задача с новой строки&#10;Например:&#10;1. Прочитать отчёт&#10;2. Встреча в 11:00&#10;3. Тренировка"
        />
      </el-form-item>

      <div class="task-preview" v-if="taskList.length">
        <el-text type="info" size="small">
          Задач: {{ taskList.length }}
        </el-text>
      </div>

      <el-button
        type="primary"
        native-type="submit"
        :loading="saving"
        style="width: 100%; margin-top: 8px;"
      >
        <el-icon><Check /></el-icon>
        <span>Сохранить план</span>
      </el-button>
    </el-form>
  </el-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { EditPen, Check } from '@element-plus/icons-vue'
import { useApi } from '@/composables/useApi'

const emit = defineEmits(['saved'])

const { api } = useApi()
const planText = ref('')
const saving = ref(false)

const taskList = computed(() =>
  planText.value
    .split('\n')
    .map((x) => x.trim())
    .filter(Boolean)
)

async function savePlan() {
  if (!taskList.value.length) {
    ElMessage.warning('Добавьте хотя бы одну задачу')
    return
  }
  saving.value = true
  try {
    await api.post('/api/plan/today', { tasks: taskList.value })
    ElMessage.success('План сохранён')
    planText.value = ''
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
  color: var(--el-color-primary);
}

.task-preview {
  margin-bottom: 4px;
}
</style>
