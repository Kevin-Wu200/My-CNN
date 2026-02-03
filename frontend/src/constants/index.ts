export const API_BASE_URL = '/api'

export const API_ENDPOINTS = {
  // Training
  TRAINING_UPLOAD: '/training/upload',
  TRAINING_PREPROCESS: '/training/preprocess',
  TRAINING_CONFIG: '/training/config',
  TRAINING_START: '/training/start',
  TRAINING_STOP: '/training/stop',
  TRAINING_STATUS: '/training/status',

  // Detection
  DETECTION_UPLOAD: '/training/upload-detection-images',
  DETECTION_RESULT: '/detection/result',
  DETECTION_GEOJSON: '/detection/geojson',

  // History
  HISTORY_TRAINING: '/history/training',
  HISTORY_DETECTION: '/history/detection',
  HISTORY_DETAIL: '/history/detail',
  HISTORY_EXPORT: '/history/export',
}

export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  INTERNAL_ERROR: 500,
}

export const ERROR_MESSAGES = {
  NETWORK_ERROR: '网络连接失败，请检查网络设置',
  SERVER_ERROR: '服务器错误，请稍后重试',
  INVALID_FILE: '文件格式不正确',
  FILE_TOO_LARGE: '文件过大，请选择较小的文件',
  UNAUTHORIZED: '未授权，请重新登录',
  UNKNOWN_ERROR: '发生未知错误，请稍后重试',
}

export const FILE_FORMATS = {
  DETECTION_IMAGE: {
    extensions: ['.jpg', '.jpeg', '.png', '.tif', '.tiff'],
    description: 'jpg、jpeg、png、tif、tiff',
  },
  TRAINING_SAMPLE: {
    extensions: ['.zip', '.rar'],
    description: 'zip、rar',
  },
  TRAINING_IMAGE: {
    extensions: ['.jpg', '.jpeg', '.png', '.tif', '.tiff'],
    description: 'jpg、jpeg、png、tif、tiff',
  },
}

export const UPLOAD_TOOLTIPS = {
  TRAINING_SAMPLE: {
    title: '训练样本上传说明',
    sections: [
      {
        heading: '压缩包结构说明：',
        content: [
          'images/',
          '存放训练影像文件，支持 jpg / png / tif',
          'labels.geojson',
          '样本标注文件，包含病害区域矢量信息',
          'meta.json（可选）',
          '数据集元信息（时间、传感器、分辨率等）',
        ],
      },
      {
        heading: '命名与规则说明：',
        content: [
          '影像文件名按时间顺序，用阿拉伯数字从1开始排列命名（例：1.img、2.img、3.img...）',
          '坐标系统需保持一致',
          '单一压缩包对应一个训练任务',
        ],
      },
    ],
  },
}

// ============ 中断类型定义 ============
// 前端假中断：由于页面刷新、路由切换、组件卸载等原因导致前端状态丢失，但实际计算任务并未在后端被主动终止
// 后端真中断：由于计算异常、Worker崩溃、后端推理失败等原因，任务在计算层面被实际终止

export const INTERRUPT_TYPES = {
  // 前端假中断 - 前端连接丢失但后端任务可能仍在运行
  FRONTEND_PAGE_REFRESH: 'frontend_page_refresh',
  FRONTEND_ROUTE_CHANGE: 'frontend_route_change',
  FRONTEND_COMPONENT_UNMOUNT: 'frontend_component_unmount',
  FRONTEND_CONNECTION_LOST: 'frontend_connection_lost',

  // 后端真中断 - 任务在计算层面被实际终止
  BACKEND_COMPUTATION_ERROR: 'backend_computation_error',
  BACKEND_WORKER_CRASH: 'backend_worker_crash',
  BACKEND_INFERENCE_FAILED: 'backend_inference_failed',
  BACKEND_TIMEOUT: 'backend_timeout',
  BACKEND_MANUAL_ABORT: 'backend_manual_abort',
} as const

export const INTERRUPT_TYPE_CATEGORIES = {
  // 前端假中断分类
  FRONTEND_INTERRUPT: 'frontend_interrupt',
  // 后端真中断分类
  BACKEND_INTERRUPT: 'backend_interrupt',
} as const

// 中断类型到分类的映射
export const INTERRUPT_TYPE_TO_CATEGORY = {
  [INTERRUPT_TYPES.FRONTEND_PAGE_REFRESH]: INTERRUPT_TYPE_CATEGORIES.FRONTEND_INTERRUPT,
  [INTERRUPT_TYPES.FRONTEND_ROUTE_CHANGE]: INTERRUPT_TYPE_CATEGORIES.FRONTEND_INTERRUPT,
  [INTERRUPT_TYPES.FRONTEND_COMPONENT_UNMOUNT]: INTERRUPT_TYPE_CATEGORIES.FRONTEND_INTERRUPT,
  [INTERRUPT_TYPES.FRONTEND_CONNECTION_LOST]: INTERRUPT_TYPE_CATEGORIES.FRONTEND_INTERRUPT,
  [INTERRUPT_TYPES.BACKEND_COMPUTATION_ERROR]: INTERRUPT_TYPE_CATEGORIES.BACKEND_INTERRUPT,
  [INTERRUPT_TYPES.BACKEND_WORKER_CRASH]: INTERRUPT_TYPE_CATEGORIES.BACKEND_INTERRUPT,
  [INTERRUPT_TYPES.BACKEND_INFERENCE_FAILED]: INTERRUPT_TYPE_CATEGORIES.BACKEND_INTERRUPT,
  [INTERRUPT_TYPES.BACKEND_TIMEOUT]: INTERRUPT_TYPE_CATEGORIES.BACKEND_INTERRUPT,
  [INTERRUPT_TYPES.BACKEND_MANUAL_ABORT]: INTERRUPT_TYPE_CATEGORIES.BACKEND_INTERRUPT,
} as const

// 中断类型对应的用户提示文案
export const INTERRUPT_MESSAGES = {
  [INTERRUPT_TYPES.FRONTEND_PAGE_REFRESH]: '页面刷新导致前端中断，任务可能仍在后台运行',
  [INTERRUPT_TYPES.FRONTEND_ROUTE_CHANGE]: '页面切换导致前端中断，任务可能仍在后台运行',
  [INTERRUPT_TYPES.FRONTEND_COMPONENT_UNMOUNT]: '组件卸载导致前端中断，任务可能仍在后台运行',
  [INTERRUPT_TYPES.FRONTEND_CONNECTION_LOST]: '前端连接已断开，任务可能仍在后台运行',
  [INTERRUPT_TYPES.BACKEND_COMPUTATION_ERROR]: '计算任务已失败：计算过程出错',
  [INTERRUPT_TYPES.BACKEND_WORKER_CRASH]: '计算任务已失败：计算进程崩溃',
  [INTERRUPT_TYPES.BACKEND_INFERENCE_FAILED]: '计算任务已失败：模型推理失败',
  [INTERRUPT_TYPES.BACKEND_TIMEOUT]: '计算任务已失败：处理超时',
  [INTERRUPT_TYPES.BACKEND_MANUAL_ABORT]: '计算任务已被中止',
} as const
