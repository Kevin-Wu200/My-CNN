<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-card">
        <div class="login-header">
          <h1>用户登录</h1>
          <p class="subtitle">遥感影像病害木检测系统</p>
        </div>

        <form @submit.prevent="handleLogin" class="login-form">
          <div class="form-group">
            <label for="phone">手机号</label>
            <input
              id="phone"
              v-model="phone"
              type="tel"
              maxlength="11"
              placeholder="请输入11位手机号"
              class="form-input"
              :class="{ 'input-error': phoneError }"
              @input="validatePhone"
              :disabled="isLoading"
            />
            <span v-if="phoneError" class="error-message">{{ phoneError }}</span>
          </div>

          <button
            type="submit"
            class="login-button"
            :disabled="!isPhoneValid || isLoading"
          >
            {{ isLoading ? '登录中...' : '登录' }}
          </button>

          <div v-if="errorMessage" class="error-alert">
            {{ errorMessage }}
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '@/services/api'
import { userStore } from '@/services/userStore'

const router = useRouter()

const phone = ref('')
const phoneError = ref('')
const errorMessage = ref('')
const isLoading = ref(false)

/**
 * 校验手机号格式
 */
const validatePhone = () => {
  if (!phone.value) {
    phoneError.value = ''
    return
  }

  if (!/^\d+$/.test(phone.value)) {
    phoneError.value = '手机号只能包含数字'
    return
  }

  if (phone.value.length !== 11) {
    phoneError.value = '手机号必须是11位'
    return
  }

  phoneError.value = ''
}

/**
 * 检查手机号是否有效
 */
const isPhoneValid = computed(() => {
  return phone.value.length === 11 && /^\d{11}$/.test(phone.value)
})

/**
 * 处理登录
 */
const handleLogin = async () => {
  // 清除之前的错误信息
  errorMessage.value = ''

  // 最后一次校验
  validatePhone()
  if (phoneError.value) {
    return
  }

  if (!isPhoneValid.value) {
    errorMessage.value = '请输入正确的手机号'
    return
  }

  isLoading.value = true

  try {
    const response = await apiClient.post('/auth/login', {
      phone: phone.value
    })

    if (response.success) {
      // 保存用户信息到store
      userStore.login({
        userId: response.data.user_id,
        phone: response.data.phone
      })

      // 跳转到检测页面
      router.push('/detection/config-selection')
    } else {
      errorMessage.value = response.message || '登录失败，请重试'
    }
  } catch (error: any) {
    console.error('登录失败:', error)
    errorMessage.value = error.message || '登录失败，请检查网络连接'
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-container {
  width: 100%;
  max-width: 420px;
}

.login-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  padding: 40px;
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  font-size: 28px;
  font-weight: 600;
  color: #1a202c;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 14px;
  color: #718096;
  margin: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: #2d3748;
}

.form-input {
  width: 100%;
  padding: 12px 16px;
  font-size: 16px;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  transition: all 0.2s;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-input:disabled {
  background-color: #f7fafc;
  cursor: not-allowed;
}

.form-input.input-error {
  border-color: #fc8181;
}

.error-message {
  font-size: 13px;
  color: #fc8181;
  margin-top: 4px;
}

.login-button {
  width: 100%;
  padding: 14px;
  font-size: 16px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  margin-top: 8px;
}

.login-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.login-button:active:not(:disabled) {
  transform: translateY(0);
}

.login-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.error-alert {
  padding: 12px 16px;
  background-color: #fff5f5;
  border: 1px solid #fc8181;
  border-radius: 8px;
  color: #c53030;
  font-size: 14px;
  text-align: center;
}
</style>
