<template>
  <el-card class="section-card">
    <template #header>
      <div class="card-header">
        <span class="card-header-icon">📋</span>
        <span>Сегодня</span>
        <el-button
          size="small"
          circle
          :loading="loading"
          @click="$emit('refresh')"
          style="margin-left: auto;"
        >
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </template>

    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>

    <el-empty
      v-else-if="!tasks.length"
      description="На сегодня плана нет"
      :image-size="80"
    >
      <template #image>
        <span style="font-size: 48px;">📝</span>
      </template>
    </el-empty>

    <template v-else>
      <div class="plan-date">
        <el-text type="info" size="small">
          {{ formatDate(planDate) }}
        </el-text>
      </div>
      <TaskCard
        v-for="task in tasks"
        :key="task.id"
        :task="task"
        @updated="$emit('refresh')"
      />
    </template>
  </el-card>
</template>

<script setup>
import { Refresh } from '@element-plus/icons-vue'
import TaskCard from './TaskCard.vue'
import { formatDate } from '@/utils/formatters'

defineProps({
  tasks: {
    type: Array,
    default: () => [],
  },
  planDate: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['refresh'])
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

.loading-container {
  padding: 8px 0;
}

.plan-date {
  margin-bottom: 12px;
}
</style>
