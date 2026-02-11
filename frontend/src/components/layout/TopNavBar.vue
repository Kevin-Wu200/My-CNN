<template>
  <header class="top-nav-bar">
    <div class="nav-left">
      <div class="logo-section">
        <img src="@/assets/logo/logo.png" alt="Logo" class="logo" />
        <span class="system-name">病害木检测系统</span>
      </div>
    </div>

    <div class="nav-center">
      <h1 class="module-title">{{ currentModuleTitle }}</h1>
    </div>

    <div class="nav-right">
      <span class="user-name">{{ userName }}</span>
      <button class="logout-btn" @click="handleLogout">退出</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { userStore } from '@/services/userStore'

const route = useRoute()
const router = useRouter()

const moduleTitle: Record<string, string> = {
  '/training/upload': '训练样本上传',
  '/training/preprocess': '样本构建与预处理',
  '/training/model-config': '模型构建与参数配置',
  '/training/training': '模型训练',
  '/detection/config-selection': '选择模型参数配置',
  '/detection/upload': '待检测影像上传',
  '/detection/result': '检测结果展示',
  '/detection/geojson': 'GeoJSON 修正与回流',
  '/unsupervised/upload': '非监督病害木检测',
  '/unsupervised/result': '检测结果',
  '/history': '历史任务管理',
  '/task-progress': '任务进度',
}

const currentModuleTitle = computed(() => {
  return moduleTitle[route.path] || '系统'
})

const userName = computed(() => {
  const phone = userStore.getPhone()
  if (phone) {
    // 格式化手机号显示：138****0000
    return phone.slice(0, 3) + '****' + phone.slice(7)
  }
  return '用户'
})

const handleLogout = () => {
  // 使用userStore的logout方法
  userStore.logout()
  // 跳转到登录页
  router.push('/login')
}
</script>

<style scoped>
.top-nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  background-color: #ffffff;
  border-bottom: 1px solid #f0f0f0;
  padding: 0 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.nav-left {
  flex: 0 0 auto;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  width: 32px;
  height: 32px;
  border-radius: 6px;
}

.system-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.nav-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.module-title {
  font-size: 16px;
  font-weight: 500;
  color: #666;
  margin: 0;
}

.nav-right {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-name {
  font-size: 14px;
  color: #666;
}

.logout-btn {
  padding: 8px 16px;
  border-radius: 6px;
  background-color: #f0f0f0;
  color: #333;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background-color: #e0e0e0;
}
</style>
