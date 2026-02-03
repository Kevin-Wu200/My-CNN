<template>
  <div class="app-container">
    <TopNavBar />
    <div class="main-layout">
      <SideNavBar />
      <main class="content-area">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import TopNavBar from '@/components/layout/TopNavBar.vue'
import SideNavBar from '@/components/layout/SideNavBar.vue'
import { taskManager } from '@/services/taskManager'
import { workerManager } from '@/services/workerManager'
import { INTERRUPT_TYPES } from '@/constants'

// ============ 应用生命周期管理 ============

/**
 * 应用挂载时的初始化
 * 1. 初始化TaskManager，恢复上一次的任务状态
 * 2. 初始化Worker实例
 * 3. 设置页面卸载时的中断处理
 */
onMounted(() => {
  // 初始化TaskManager
  // 这会从localStorage恢复上一次的任务状态
  // 如果任务状态为running但Worker实例已丢失，会自动标记为前端假中断
  taskManager.initialize()
  console.log('TaskManager已初始化')

  // 初始化Worker
  // 用于处理长时间计算任务
  workerManager.initialize()
  console.log('Worker已初始化')

  // 设置页面卸载事件处理
  // 当用户关闭页面或刷新时，标记运行中的任务为前端假中断
  window.addEventListener('beforeunload', handlePageUnload)
})

/**
 * 应用卸载时的清理
 */
onUnmounted(() => {
  // 移除页面卸载事件监听
  window.removeEventListener('beforeunload', handlePageUnload)

  // 销毁Worker
  workerManager.destroy()
  console.log('Worker已销毁')
})

/**
 * 页面卸载事件处理
 * 当用户关闭页面、刷新页面或导航到其他网站时触发
 * 此时标记运行中的任务为前端假中断
 */
function handlePageUnload(): void {
  const currentTask = taskManager.getCurrentTask()

  // 如果有运行中的任务，标记为前端假中断
  if (currentTask && currentTask.status === 'running') {
    console.warn(
      `页面卸载: 任务 ${currentTask.id} 状态标记为前端假中断 (页面刷新或关闭)`
    )
    // 标记为前端假中断 - 页面刷新或关闭导致的前端连接丢失
    taskManager.markFrontendInterrupt(INTERRUPT_TYPES.FRONTEND_PAGE_REFRESH)
  }
}
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f5f5;
}

.main-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
</style>
