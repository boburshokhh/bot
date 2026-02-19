(function () {
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  const statusBar = document.getElementById("statusBar");
  const todayBlock = document.getElementById("todayBlock");
  const statsBlock = document.getElementById("statsBlock");
  const historyBlock = document.getElementById("historyBlock");

  function setStatus(message, isError) {
    statusBar.textContent = message;
    statusBar.className = `status ${isError ? "err" : "ok"}`;
  }

  function getInitData() {
    if (tg && tg.initData) {
      return tg.initData;
    }
    const p = new URLSearchParams(window.location.search);
    return p.get("initData") || "";
  }

  async function api(path, options) {
    const initData = getInitData();
    const resp = await fetch(path, {
      method: options && options.method ? options.method : "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": initData,
      },
      body: options && options.body ? JSON.stringify(options.body) : undefined,
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

  function taskStatusLabel(value) {
    if (value === "done") return "✅ выполнено";
    if (value === "partial") return "⚠ частично";
    if (value === "failed") return "❌ не выполнено";
    return "— не отмечено";
  }

  function renderToday(data) {
    if (!data.tasks || data.tasks.length === 0) {
      todayBlock.innerHTML = `<div>На сегодня плана нет.</div>`;
      return;
    }
    const rows = data.tasks.map((task) => {
      const comment = task.comment ? `<div class="muted">Комментарий: ${task.comment}</div>` : "";
      return `
        <div class="task">
          <div><strong>${task.position + 1}. ${task.text}</strong></div>
          <div class="muted">Статус: ${taskStatusLabel(task.status)}</div>
          ${comment}
          <div class="row">
            <button data-task="${task.id}" data-status="done">✅</button>
            <button data-task="${task.id}" data-status="partial">⚠</button>
            <button data-task="${task.id}" data-status="failed">❌</button>
          </div>
          <div class="row">
            <input id="comment-${task.id}" placeholder="Комментарий (опционально)" />
            <button class="secondary" data-comment-task="${task.id}">Сохранить комментарий</button>
          </div>
        </div>
      `;
    });
    todayBlock.innerHTML = rows.join("");

    document.querySelectorAll("[data-status]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api(`/api/tasks/${btn.dataset.task}/status`, {
            method: "PUT",
            body: { status: btn.dataset.status },
          });
          setStatus("Статус обновлён", false);
          await loadToday();
          await loadStats();
        } catch (err) {
          setStatus(err.message, true);
        }
      });
    });

    document.querySelectorAll("[data-comment-task]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.commentTask;
        const comment = document.getElementById(`comment-${id}`).value || "";
        try {
          await api(`/api/tasks/${id}/status`, { method: "PUT", body: { comment } });
          setStatus("Комментарий обновлён", false);
          await loadToday();
        } catch (err) {
          setStatus(err.message, true);
        }
      });
    });
  }

  function renderStats(data) {
    statsBlock.innerHTML = `
      <div>Всего планов: <strong>${data.total_plans}</strong></div>
      <div>Средний % выполнения: <strong>${data.avg_percent}%</strong></div>
      <div>Текущий стрик: <strong>${data.current_streak}</strong></div>
    `;
  }

  function renderHistory(data) {
    if (!data.items || data.items.length === 0) {
      historyBlock.innerHTML = "<div>За выбранный месяц данных нет.</div>";
      return;
    }
    historyBlock.innerHTML = data.items
      .map((x) => `<div>${x.date}: ${x.done}/${x.total} (${x.percent}%)</div>`)
      .join("");
  }

  async function loadToday() {
    const data = await api("/api/today");
    renderToday(data);
  }

  async function loadSettings() {
    const s = await api("/api/settings");
    document.getElementById("tzInput").value = s.timezone;
    document.getElementById("morningInput").value = s.morning_time;
    document.getElementById("eveningInput").value = s.evening_time;
    document.getElementById("intervalInput").value = String(s.reminder_interval_minutes);
    document.getElementById("attemptsInput").value = String(s.reminder_max_attempts);
  }

  async function loadStats() {
    const s = await api("/api/stats");
    renderStats(s);
  }

  async function loadHistory(month) {
    const m = month || new Date().toISOString().slice(0, 7);
    document.getElementById("historyMonthInput").value = m;
    const h = await api(`/api/history?month=${encodeURIComponent(m)}`);
    renderHistory(h);
  }

  document.getElementById("savePlanBtn").addEventListener("click", async () => {
    const raw = document.getElementById("planTasks").value || "";
    const tasks = raw.split("\n").map((x) => x.trim()).filter(Boolean);
    try {
      await api("/api/plan/today", { method: "POST", body: { tasks } });
      setStatus("План сохранён", false);
      document.getElementById("planTasks").value = "";
      await loadToday();
      await loadStats();
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  document.getElementById("saveSettingsBtn").addEventListener("click", async () => {
    const payload = {
      timezone: document.getElementById("tzInput").value.trim(),
      morning_time: document.getElementById("morningInput").value.trim(),
      evening_time: document.getElementById("eveningInput").value.trim(),
      reminder_interval_minutes: Number(document.getElementById("intervalInput").value),
      reminder_max_attempts: Number(document.getElementById("attemptsInput").value),
    };
    try {
      await api("/api/settings", { method: "PUT", body: payload });
      setStatus("Настройки сохранены", false);
      await loadSettings();
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  document.getElementById("loadHistoryBtn").addEventListener("click", async () => {
    try {
      await loadHistory(document.getElementById("historyMonthInput").value.trim());
      setStatus("История обновлена", false);
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  (async function init() {
    try {
      await Promise.all([loadToday(), loadSettings(), loadStats(), loadHistory()]);
      setStatus("WebApp готов", false);
    } catch (err) {
      setStatus(err.message, true);
    }
  })();
})();
