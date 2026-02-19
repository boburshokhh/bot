<template>
  <el-card class="section-card">
    <template #header>
      <div class="card-header">
        <span class="card-header-icon">📊</span>
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
          <el-statistic :value="stats.current_streak || 0" title="Стрик" suffix=" 🔥" />
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
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
}

.stats-row {
  text-align: center;
}

.stat-item {
  padding: 12px 4px;
  background: var(--el-fill-color-light);
  border-radius: 12px;
}
</style>
