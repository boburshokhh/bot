import { useWebApp } from './useWebApp'

export function useApi() {
  const { getInitData } = useWebApp()

  async function request(path, options = {}) {
    const initData = getInitData()
    const resp = await fetch(path, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': initData,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    })

    if (!resp.ok) {
      let msg = `HTTP ${resp.status}`
      try {
        const err = await resp.json()
        msg = err.detail || msg
      } catch (_) {}
      throw new Error(msg)
    }

    return resp.json()
  }

  const api = {
    get: (path) => request(path),
    post: (path, body) => request(path, { method: 'POST', body }),
    put: (path, body) => request(path, { method: 'PUT', body }),
    delete: (path) => request(path, { method: 'DELETE' }),
  }

  return { api }
}
