import { reactive } from 'vue'

const state = reactive({
  message: '',
  visible: false,
  timer: null,
})

export function showAuthError(msg = 'API Key 未配置或无效，请在设置中配置正确的 API Key') {
  if (state.timer) clearTimeout(state.timer)
  state.message = msg
  state.visible = true
  state.timer = setTimeout(() => {
    state.visible = false
  }, 5000)
}

export function hideAuthError() {
  if (state.timer) clearTimeout(state.timer)
  state.visible = false
}

export function useAuthError() {
  return state
}
