import { ref, computed } from 'vue'

export const useLoading = () => {
  const isLoading = ref(false)

  const setLoading = (value: boolean) => {
    isLoading.value = value
  }

  return {
    isLoading: computed(() => isLoading.value),
    setLoading,
  }
}

export const useError = () => {
  const error = ref<string | null>(null)

  const setError = (message: string | null) => {
    error.value = message
  }

  const clearError = () => {
    error.value = null
  }

  return {
    error: computed(() => error.value),
    setError,
    clearError,
  }
}

export const useSuccess = () => {
  const success = ref<string | null>(null)

  const setSuccess = (message: string | null) => {
    success.value = message
    if (message) {
      setTimeout(() => {
        success.value = null
      }, 3000)
    }
  }

  return {
    success: computed(() => success.value),
    setSuccess,
  }
}
