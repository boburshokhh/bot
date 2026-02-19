<template>
  <el-card class="section-card">
    <template #header>
      <div class="card-header">
        <span class="card-header-icon">📅</span>
        <span>История</span>
      </div>
    </template>

    <div class="month-picker-row">
      <el-date-picker
        v-model="selectedMonth"
        type="month"
        format="YYYY-MM"
        value-format="YYYY-MM"
        placeholder="Выберите месяц"
        style="flex: 1;"
      />
      <el-button :loading="loading" @click="loadHistory">Загрузить</el-button>
    </div>

    <div v-if="loading" style="margin-top: 16px;">
      <el-skeleton :rows="3" animated />
    </div>

    <el-empty
      v-else-if="!items.length && loaded"
      description="За выбранный месяц данных нет"
      :image-size="60"
      style="margin-top: 16px;"
    >
      <template #image>
        <span style="font-size: 40px;">📭</span>
      </template>
    </el-empty>

    <div v-else-if="items.length" class="history-list">
      <div
        v-for="item in items"
        :key="item.date"
        class="history-item"
      >
        <div class="history-info">
          <span class="history-date">{{ formatDate(item.date) }}</span>
          <el-tag
            :type="getPercentType(item.percent)"
            size="small"
            round
          >
            {{ item.done }}/{{ item.total }} ({{ item.percent }}%)
          </el-tag>
        </div>
        <el-progress
          :percentage="item.percent"
          :status="getProgressStatus(item.percent)"
          :stroke-width="6"
          :show-text="false"
          style="margin-top: 6px;"
        />
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useApi } from '@/composables/useApi'
import { formatDate } from '@/utils/formatters'

const { api } = useApi()

const selectedMonth = ref(new Date().toISOString().slice(0, 7))
const items = ref([])
const loading = ref(false)
const loaded = ref(false)

function getPercentType(percent) {
  if (percent >= 80) return 'success'
  if (percent >= 50) return 'warning'
  return 'danger'
}

function getProgressStatus(percent) {
  if (percent >= 80) return 'success'
  if (percent >= 50) return ''
  return 'exception'
}

async function loadHistory() {
  loading.value = true
  loaded.value = false
  try {
    const month = selectedMonth.value || new Date().toISOString().slice(0, 7)
    const h = await api.get(`/api/history?month=${encodeURIComponent(month)}`)
    items.value = h.items || []
    loaded.value = true
  } catch (err) {
    ElMessage.error('Ошибка загрузки истории: ' + err.message)
  } finally {
    loading.value = false
  }
}

loadHistory()
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

.month-picker-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.history-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-item {
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 10px;
}

.history-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.history-date {
  font-weight: 500;
  font-size: 14px;
}
</style>
