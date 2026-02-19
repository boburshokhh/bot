export function formatDate(dateStr) {
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

export function getStatusLabel(status) {
  const labels = {
    done: 'Выполнено',
    partial: 'Частично',
    failed: 'Не выполнено',
  }
  return labels[status] || 'Не отмечено'
}

export function getStatusType(status) {
  const types = {
    done: 'success',
    partial: 'warning',
    failed: 'danger',
  }
  return types[status] || 'info'
}
