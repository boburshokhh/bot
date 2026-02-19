<template>
  <el-card class="section-card">
    <template #header>
      <div class="card-header">
        <el-icon class="card-header-icon"><DataAnalysis /></el-icon>
        <span>Статистика</span>
      </div>
    </template>

    <div v-if="loading">
      <el-skeleton :rows="2" animated />
    </div>

    <el-row v-else :gutter="12" class="stats-row">
      <el-col :span="8">
        <div class="stat-item">
          <el-statistic :value="stats.total_plans || 0" title="Планов" />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-item">
          <el-statistic :value="stats.avg_percent || 0" title="Средний %" suffix="%" />
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-item">
          <el-statistic :value="stats.current_streak || 0" title="Стрик">
            <template #suffix>
              <el-icon class="streak-icon"><TrendCharts /></el-icon>
            </template>
          </el-statistic>
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
import { DataAnalysis, TrendCharts } from '@element-plus/icons-vue'

defineProps({
  stats: {
    type: Object,
    default: () => ({ total_plans: 0, avg_percent: 0, current_streak: 0 }),
  },
  loading: {
    type: Boolean,
    default: false,
  },
})
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

.stats-row {
  text-align: center;
}

.stat-item {
  padding: 12px 4px;
  background: var(--el-fill-color-light);
  border-radius: 12px;
}

.streak-icon {
  color: var(--el-color-warning);
  font-size: 16px;
  margin-left: 2px;
}

@media (max-width: 768px) {
  .el-col {
    margin-bottom: 8px;
  }
  
  .stat-item {
    padding: 10px 2px;
  }
}
</style>
