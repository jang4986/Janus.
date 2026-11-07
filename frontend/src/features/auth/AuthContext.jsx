import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { setToken, getToken, getRefreshToken } from '@/shared/api/client'
import * as authApi from './api/authApi'

const AuthContext = createContext(null)

/**
 * Quản lý phiên đăng nhập: token lưu ở localStorage, hồ sơ lấy lại từ
 * GET /v1/profile mỗi lần mở trang để tránh hiển thị trạng thái giả.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    if (!getToken()) {
      setReady(true)
      return undefined
    }
    authApi
      .fetchProfile()
      .then((profile) => {
        if (!cancelled) setUser(profile)
      })
      .catch((requestError) => {
        if (!cancelled) {
          // Chỉ xóa phiên khi backend xác nhận token không hợp lệ/hết hạn.
          // Lỗi 500 hoặc mất kết nối tạm thời không nên làm mất phiên đăng nhập.
          if (requestError.status === 401) setToken(null)
          setUser(null)
        }
      })
      .finally(() => {
        if (!cancelled) setReady(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email, password) => {
    const session = await authApi.login(email, password)
    setToken(session.access_token)
    const profile = await authApi.fetchProfile()
    setUser(profile)
    return profile
  }, [])

  const register = useCallback(
    async (input) => {
      await authApi.register(input)
      // Backend không trả token khi đăng ký nên đăng nhập lại ngay để giữ luồng UX liền mạch.
      return login(input.email, input.password)
    },
    [login],
  )

  const updateProfile = useCallback(async (input) => {
    const profile = await authApi.updateProfile(input)
    setUser(profile)
    return profile
  }, [])

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken()
    try {
      await authApi.logout(refreshToken)
    } catch {
      // Clear the local session even if the backend is unreachable.
    }
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, ready, isAuthenticated: Boolean(user), login, register, updateProfile, logout }),
    [user, ready, login, register, updateProfile, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth phải được dùng bên trong <AuthProvider>')
  return context
}
