(function () {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    // Настройка темы Telegram
    if (tg.colorScheme === 'dark') {
      document.documentElement.style.setProperty('--bg', '#1f2937');
      document.documentElement.style.setProperty('--card-bg', '#374151');
      document.documentElement.style.setProperty('--text', '#f9fafb');
      document.documentElement.style.setProperty('--text-muted', '#d1d5db');
      document.documentElement.style.setProperty('--border', '#4b5563');
    }
  }

  function getInitData() {
    if (tg?.initData) {
      return tg.initData;
    }
    const p = new URLSearchParams(window.location.search);
    return p.get("initData") || "";
  }

  async function api(path, options = {}) {
    const initData = getInitData();
    const resp = await fetch(path, {
      method: options.method || "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": initData,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    if (!resp.ok) {
      let msg = `HTTP ${resp.status}`;
      try {
        const err = await resp.json();
        msg = err.detail || msg;
      } catch (_) {}
      throw new Error(msg);
    }
    return resp.json();
  }

  function webapp() {
    return {
      loading: {
        today: true,
        stats: true,
        history: false,
        settings: true,
      },
      today: {
        tasks: [],
        date: null,
        exists: false,
      },
      stats: {
        total_plans: 0,
        avg_percent: 0,
        current_streak: 0,
      },
      history: {
        items: [],
        month: new Date().toISOString().slice(0, 7),
      },
      settings: {
        timezone: "",
        morning_time: "",
        evening_time: "",
        reminder_interval_minutes: 60,
        reminder_max_attempts: 1,
      },
      newPlanText: "",
      historyMonth: new Date().toISOString().slice(0, 7),
      status: {
        show: false,
        message: "",
        type: "success",
      },

      async init() {
        await Promise.all([
          this.loadToday(),
          this.loadSettings(),
          this.loadStats(),
          this.loadHistory(),
        ]);
        this.showStatus("WebApp готов", "success");
      },

      showStatus(message, type = "success") {
        this.status.message = message;
        this.status.type = type;
        this.status.show = true;
        setTimeout(() => {
          this.status.show = false;
        }, 3000);
      },

      getStatusLabel(status) {
        const labels = {
          done: "✅ выполнено",
          partial: "⚠ частично",
          failed: "❌ не выполнено",
        };
        return labels[status] || "— не отмечено";
      },

      formatDate(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleDateString("ru-RU", {
          year: "numeric",
          month: "long",
          day: "numeric",
        });
      },

      async loadToday() {
        this.loading.today = true;
        try {
          const data = await api("/api/today");
          this.today = data;
        } catch (err) {
          this.showStatus("Ошибка загрузки плана: " + err.message, "error");
        } finally {
          this.loading.today = false;
        }
      },

      async loadSettings() {
        this.loading.settings = true;
        try {
          const s = await api("/api/settings");
          this.settings = {
            timezone: s.timezone || "",
            morning_time: s.morning_time || "",
            evening_time: s.evening_time || "",
            reminder_interval_minutes: s.reminder_interval_minutes || 60,
            reminder_max_attempts: s.reminder_max_attempts || 1,
          };
        } catch (err) {
          this.showStatus("Ошибка загрузки настроек: " + err.message, "error");
        } finally {
          this.loading.settings = false;
        }
      },

      async loadStats() {
        this.loading.stats = true;
        try {
          const s = await api("/api/stats");
          this.stats = s;
        } catch (err) {
          this.showStatus("Ошибка загрузки статистики: " + err.message, "error");
        } finally {
          this.loading.stats = false;
        }
      },

      async loadHistory() {
        this.loading.history = true;
        try {
          const month = this.historyMonth || new Date().toISOString().slice(0, 7);
          const h = await api(`/api/history?month=${encodeURIComponent(month)}`);
          this.history = h;
        } catch (err) {
          this.showStatus("Ошибка загрузки истории: " + err.message, "error");
        } finally {
          this.loading.history = false;
        }
      },

      async savePlan() {
        const raw = this.newPlanText || "";
        const tasks = raw
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean);
        if (tasks.length === 0) {
          this.showStatus("Добавьте хотя бы одну задачу", "error");
          return;
        }
        try {
          await api("/api/plan/today", {
            method: "POST",
            body: { tasks },
          });
          this.showStatus("План сохранён", "success");
          this.newPlanText = "";
          await Promise.all([this.loadToday(), this.loadStats()]);
        } catch (err) {
          this.showStatus("Ошибка: " + err.message, "error");
        }
      },

      async saveSettings() {
        try {
          await api("/api/settings", {
            method: "PUT",
            body: {
              timezone: this.settings.timezone?.trim() || null,
              morning_time: this.settings.morning_time?.trim() || null,
              evening_time: this.settings.evening_time?.trim() || null,
              reminder_interval_minutes:
                this.settings.reminder_interval_minutes || null,
              reminder_max_attempts: this.settings.reminder_max_attempts || null,
            },
          });
          this.showStatus("Настройки сохранены", "success");
          await this.loadSettings();
        } catch (err) {
          this.showStatus("Ошибка: " + err.message, "error");
        }
      },

      async updateTaskStatus(taskId, status) {
        try {
          await api(`/api/tasks/${taskId}/status`, {
            method: "PUT",
            body: { status },
          });
          this.showStatus("Статус обновлён", "success");
          await Promise.all([this.loadToday(), this.loadStats()]);
        } catch (err) {
          this.showStatus("Ошибка: " + err.message, "error");
        }
      },

      async saveComment(taskId) {
        const input = document.getElementById(`comment-${taskId}`);
        const comment = input?.value?.trim() || "";
        try {
          await api(`/api/tasks/${taskId}/status`, {
            method: "PUT",
            body: { comment },
          });
          this.showStatus("Комментарий сохранён", "success");
          await this.loadToday();
        } catch (err) {
          this.showStatus("Ошибка: " + err.message, "error");
        }
      },
    };
  }

  // Экспортируем функцию для Alpine.js
  window.webapp = webapp;
})();
