import { ref, computed } from 'vue'

export const useNavigation = () => {
  const currentModule = ref('')

  const moduleTitle = computed(() => {
    const titles: Record<string, string> = {
      '/training/upload': '训练样本上传',
      '/training/preprocess': '样本构建与预处理',
      '/training/model-config': '模型构建与参数配置',
      '/training/training': '模型训练',
      '/detection/upload': '待检测影像上传',
      '/detection/result': '检测结果展示',
      '/detection/geojson': 'GeoJSON 修正与回流',
      '/history': '历史任务管理',
    }
    return titles[currentModule.value] || '系统'
  })

  return {
    currentModule,
    moduleTitle,
  }
}

export const useUser = () => {
  const userName = ref(localStorage.getItem('userName') || '用户')
  const token = ref(localStorage.getItem('token') || '')

  const setUser = (name: string, authToken: string) => {
    userName.value = name
    token.value = authToken
    localStorage.setItem('userName', name)
    localStorage.setItem('token', authToken)
  }

  const logout = () => {
    userName.value = '用户'
    token.value = ''
    localStorage.removeItem('userName')
    localStorage.removeItem('token')
  }

  return {
    userName,
    token,
    setUser,
    logout,
  }
}
