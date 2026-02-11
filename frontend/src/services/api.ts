import axios, { AxiosInstance, AxiosError } from 'axios'
import type { ApiResponse } from '@/types'
import { userStore } from '@/services/userStore'

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: '/api',
      timeout: 43200000,  // 12小时
    })

    // 请求拦截器 - 自动添加用户ID
    this.client.interceptors.request.use(
      (config) => {
        const userId = userStore.getUserId()

        // 只有在用户已登录且不是登录接口时才添加user_id
        if (userId && !config.url?.includes('/auth/login')) {
          if (config.method === 'get') {
            // GET请求：添加到params
            config.params = { ...config.params, user_id: userId }
          } else if (config.method === 'post' || config.method === 'put') {
            // POST/PUT请求：根据数据类型添加
            if (config.data instanceof FormData) {
              // FormData类型：使用append
              config.data.append('user_id', userId.toString())
            } else if (config.data) {
              // 普通对象：添加到data
              config.data = { ...config.data, user_id: userId }
            }
          }
        }

        return config
      },
      (error) => Promise.reject(error)
    )

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response.data,
      (error: AxiosError) => {
        const message = error.response?.data?.message || error.message || '请求失败'
        return Promise.reject({
          code: error.response?.status || 500,
          message,
        })
      }
    )
  }

  async get<T>(url: string, config?: any): Promise<ApiResponse<T>> {
    return this.client.get(url, config)
  }

  async post<T>(url: string, data?: any, config?: any): Promise<ApiResponse<T>> {
    // 超时时间设置为12小时
    const timeout = 43200000
    return this.client.post(url, data, { timeout, ...config })
  }

  async put<T>(url: string, data?: any, config?: any): Promise<ApiResponse<T>> {
    return this.client.put(url, data, config)
  }

  async delete<T>(url: string, config?: any): Promise<ApiResponse<T>> {
    return this.client.delete(url, config)
  }

  async upload<T>(url: string, file: File, config?: any): Promise<ApiResponse<T>> {
    const formData = new FormData()
    formData.append('file', file)
    return this.client.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      ...config,
    })
  }
}

export const apiClient = new ApiClient()
