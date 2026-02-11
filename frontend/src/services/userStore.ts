/**
 * 用户状态管理模块
 * 提供用户登录、登出、用户信息存储和持久化功能
 */

interface UserInfo {
  userId: number
  phone: string
  createdAt?: string
  lastLogin?: string
}

class UserStore {
  private static instance: UserStore
  private userInfo: UserInfo | null = null
  private readonly STORAGE_KEY = 'user_info'

  private constructor() {
    this.loadFromStorage()
  }

  /**
   * 获取UserStore单例实例
   */
  static getInstance(): UserStore {
    if (!UserStore.instance) {
      UserStore.instance = new UserStore()
    }
    return UserStore.instance
  }

  /**
   * 用户登录，保存用户信息
   */
  login(userInfo: UserInfo): void {
    this.userInfo = userInfo
    this.saveToStorage()
  }

  /**
   * 用户登出，清除用户信息
   */
  logout(): void {
    this.userInfo = null
    localStorage.removeItem(this.STORAGE_KEY)
  }

  /**
   * 获取当前用户信息
   */
  getUserInfo(): UserInfo | null {
    return this.userInfo
  }

  /**
   * 检查用户是否已登录
   */
  isLoggedIn(): boolean {
    return this.userInfo !== null
  }

  /**
   * 获取当前用户ID
   */
  getUserId(): number | null {
    return this.userInfo?.userId || null
  }

  /**
   * 获取当前用户手机号
   */
  getPhone(): string | null {
    return this.userInfo?.phone || null
  }

  /**
   * 从localStorage加载用户信息
   */
  private loadFromStorage(): void {
    const stored = localStorage.getItem(this.STORAGE_KEY)
    if (stored) {
      try {
        this.userInfo = JSON.parse(stored)
      } catch (e) {
        console.error('Failed to parse user info from storage', e)
        localStorage.removeItem(this.STORAGE_KEY)
      }
    }
  }

  /**
   * 保存用户信息到localStorage
   */
  private saveToStorage(): void {
    if (this.userInfo) {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.userInfo))
    }
  }
}

// 导出单例实例
export const userStore = UserStore.getInstance()
export type { UserInfo }
