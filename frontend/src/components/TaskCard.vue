<template>
  <el-card class="task-card" shadow="never">
    <div class="task-header">
      <div class="task-meta">
        <span class="task-number">{{ task.position + 1 }}.</span>
        <span class="task-text">{{ task.text }}</span>
      </div>
      <el-tag
        :type="statusType"
        size="small"
        round
        class="task-status-tag"
      >
        {{ statusLabel }}
      </el-tag>
    </div>

    <div class="task-actions">
      <el-button
        type="success"
        size="small"
        :loading="loading === 'done'"
        @click="setStatus('done')"
      >
        <el-icon><CircleCheck /></el-icon>
        <span class="btn-text">Выполнено</span>
      </el-button>
      <el-button
        type="warning"
        size="small"
        :loading="loading === 'partial'"
        @click="setStatus('partial')"
      >
        <el-icon><Warning /></el-icon>
        <span class="btn-text">Частично</span>
      </el-button>
      <el-button
        type="danger"
        size="small"
        :loading="loading === 'failed'"
        @click="setStatus('failed')"
      >
        <el-icon><CircleClose /></el-icon>
        <span class="btn-text">Не выполнено</span>
      </el-button>
    </div>

    <div class="task-comment-row">
      <el-input
        v-model="commentText"
        :placeholder="`Комментарий к задаче ${task.position + 1}`"
        size="small"
        clearable
      >
        <template #prefix>
          <el-icon><ChatLineRound /></el-icon>
        </template>
      </el-input>
      <el-button
        size="small"
        :loading="savingComment"
        @click="saveComment"
        type="primary"
      >
        <el-icon><Check /></el-icon>
      </el-button>
    </div>

    <div v-if="task.comment" class="task-comment">
      <el-icon class="comment-icon"><ChatLineRound /></el-icon>
      <span>{{ task.comment }}</span>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CircleCheck,
  Warning,
  CircleClose,
  ChatLineRound,
  Check,
} from '@element-plus/icons-vue'
import { useApi } from '@/composables/useApi'
import { getStatusLabel, getStatusType } from '@/utils/formatters'

const props = defineProps({
  task: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['updated'])

const { api } = useApi()
const loading = ref(null)
const savingComment = ref(false)
const commentText = ref(props.task.comment || '')

const statusLabel = computed(() => getStatusLabel(props.task.status))
const statusType = computed(() => getStatusType(props.task.status))

async function setStatus(status) {
  loading.value = status
  try {
    await api.put(`/api/tasks/${props.task.id}/status`, { status })
    ElMessage.success('Статус обновлён')
    emit('updated')
  } catch (err) {
    ElMessage.error('Ошибка: ' + err.message)
  } finally {
    loading.value = null
  }
}

async function saveComment() {
  savingComment.value = true
  try {
    await api.put(`/api/tasks/${props.task.id}/status`, {
      comment: commentText.value.trim(),
    })
    ElMessage.success('Комментарий сохранён')
    emit('updated')
  } catch (err) {
    ElMessage.error('Ошибка: ' + err.message)
  } finally {
    savingComment.value = false
  }
}
</script>

<style scoped>
.task-card {
  margin-bottom: 12px;
  border-radius: 12px;
}

.task-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.task-meta {
  flex: 1;
  line-height: 1.5;
}

.task-number {
  font-weight: 700;
  color: var(--el-color-primary);
  margin-right: 6px;
}

.task-text {
  font-size: 14px;
}

.task-status-tag {
  flex-shrink: 0;
}

.task-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.task-actions .el-button {
  flex: 1;
  min-width: 0;
}

.btn-text {
  margin-left: 4px;
}

@media (max-width: 480px) {
  .btn-text {
    display: none;
  }
  
  .task-actions .el-button {
    flex: 0 0 auto;
  }
}

.task-comment-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.task-comment {
  margin-top: 10px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.comment-icon {
  font-size: 14px;
  color: var(--el-color-primary);
  flex-shrink: 0;
}
</style>
