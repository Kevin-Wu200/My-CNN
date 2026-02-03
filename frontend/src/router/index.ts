import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { taskManager } from '@/services/taskManager'
import { INTERRUPT_TYPES } from '@/constants'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/detection/config-selection',
  },
  {
    path: '/task-progress',
    component: () => import('@/pages/task/TaskProgress.vue'),
    meta: { title: '任务进度' },
  },
  {
    path: '/training',
    component: () => import('@/pages/training/TrainingLayout.vue'),
    children: [
      {
        path: 'upload',
        component: () => import('@/pages/training/SampleUpload.vue'),
        meta: { title: '训练样本上传' },
      },
      {
        path: 'preprocess',
        component: () => import('@/pages/training/SamplePreprocess.vue'),
        meta: { title: '样本构建与预处理' },
      },
      {
        path: 'model-config',
        component: () => import('@/pages/training/ModelConfig.vue'),
        meta: { title: '模型构建与参数配置' },
      },
      {
        path: 'training',
        component: () => import('@/pages/training/ModelTraining.vue'),
        meta: { title: '模型训练' },
      },
    ],
  },
  {
    path: '/detection',
    component: () => import('@/pages/detection/DetectionLayout.vue'),
    children: [
      {
        path: 'config-selection',
        component: () => import('@/pages/detection/ModelConfigSelection.vue'),
        meta: { title: '选择模型参数配置' },
      },
      {
        path: 'upload',
        component: () => import('@/pages/detection/ImageUpload.vue'),
        meta: { title: '待检测影像上传' },
      },
      {
        path: 'result',
        component: () => import('@/pages/detection/DetectionResult.vue'),
        meta: { title: '检测结果展示' },
      },
      {
        path: 'geojson',
        component: () => import('@/pages/detection/GeoJSONCorrection.vue'),
        meta: { title: 'GeoJSON 修正与回流' },
      },
    ],
  },
  {
    path: '/unsupervised',
    component: () => import('@/pages/unsupervised/UnsupervisedLayout.vue'),
    children: [
      {
        path: 'upload',
        component: () => import('@/pages/unsupervised/UnsupervisedUpload.vue'),
        meta: { title: '无监督病害木检测' },
      },
      {
        path: 'result',
        component: () => import('@/pages/unsupervised/UnsupervisedResult.vue'),
        meta: { title: '检测结果' },
      },
    ],
  },
  {
    path: '/history',
    component: () => import('@/pages/history/TaskHistory.vue'),
    meta: { title: '历史任务管理' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ============ 路由守卫 - 检测路由切换时的前端假中断 ============

/**
 * 全局前置守卫
 * 在路由切换前检查是否有运行中的任务
 * 如果有，则标记为前端假中断（路由切换导致的前端连接丢失）
 *
 * 【改进】现在任务在 Worker 中执行，路由切换不会中断任务
 * 但仍然标记状态以便追踪用户行为
 */
router.beforeEach((to, from, next) => {
  // 获取当前任务状态
  const currentTask = taskManager.getCurrentTask()

  // 如果有运行中的任务且路由发生变化，标记为前端假中断
  if (currentTask && currentTask.status === 'running' && to.path !== from.path) {
    console.warn(
      `[Router] 检测到路由切换: ${from.path} -> ${to.path}，任务 ${currentTask.id} 状态标记为前端假中断`
    )
    console.log('[Router] 当前任务状态:', {
      taskId: currentTask.id,
      status: currentTask.status,
      progress: currentTask.progress,
      currentStage: currentTask.currentStage,
    })
    // 标记为前端假中断 - 路由切换导致的前端连接丢失
    // 【关键】虽然标记为假中断，但任务在 Worker 中继续执行，不会被中止
    taskManager.markFrontendInterrupt(INTERRUPT_TYPES.FRONTEND_ROUTE_CHANGE)
  }

  next()
})

export default router
