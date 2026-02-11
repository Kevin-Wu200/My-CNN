export const unsupervisedRoutes = [
  {
    path: 'upload',
    component: () => import('./UnsupervisedUpload.vue'),
    meta: { title: '非监督病害木检测' },
  },
  {
    path: 'result',
    component: () => import('./UnsupervisedResult.vue'),
    meta: { title: '检测结果' },
  },
]
