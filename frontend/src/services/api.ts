import axios, { AxiosInstance, AxiosError } from 'axios'
import type { ApiResponse } from '@/types'

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: '/api',
      timeout: 43200000,  // 12小时
    })

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
