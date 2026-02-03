import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { taskManager } from './services/taskManager'
import './styles/variables.css'
import './styles/animations.css'
import './styles/main.css'

const app = createApp(App)

/**
 * ============ 应用启动流程 ============
 *
 * 【关键】TaskManager 必须在应用挂载之前初始化
 * 这确保了 TaskManager 的生命周期独立于 Vue 应用
 * 即使 Vue 应用被销毁，TaskManager 的状态仍然存在
 *
 * 【强单例保证】
 * taskManager 是通过 TaskManagerImpl.getInstance() 获取的全局实例
 * 无论该模块被 import 多少次，都只会存在一个实例
 * 实例存储在 window.__APP_TASK_MANAGER__ 上，不会因为模块重新加载而被销毁
 */
taskManager.initialize()

app.use(router)
app.mount('#app')
