/**
 * API client dùng chung cho toàn bộ frontend.
 *
 * - Đọc base URL từ VITE_API_BASE_URL (mặc định "/api" = Vite proxy sang FastAPI backend).
 * - Quản lý cặp access_token và refresh_token trong localStorage.
 * - Tự gắn Bearer token nếu người dùng đã đăng nhập.
 * - Response Interceptor: Tự động phát hiện lỗi 401 Unauthorized và thực hiện xoay vòng token (Refresh Rotation)
 *   qua POST /api/v1/auth/refresh kèm hàng đợi/mutex (refreshPromise singleton) để tránh duplicate refresh calls.
 * - Ném ApiError có status + detail để UI hiển thị đúng thông báo từ backend.
 */

const RAW_BASE = import.meta.env?.VITE_API_BASE_URL || '/api'
const BASE_URL = RAW_BASE.endsWith('/') ? RAW_BASE.slice(0, -1) : RAW_BASE

const ACCESS_TOKEN_KEY = 'janus.access_token'
const REFRESH_TOKEN_KEY = 'janus.refresh_token'

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Yêu cầu thất bại (${status})`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail || `Yêu cầu thất bại (${status})`
  }
}

export function getToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setToken(token) {
  if (token) {
    if (typeof token === 'object') {
      if (token.access_token) localStorage.setItem(ACCESS_TOKEN_KEY, token.access_token)
      if (token.refresh_token) localStorage.setItem(REFRESH_TOKEN_KEY, token.refresh_token)
    } else {
      localStorage.setItem(ACCESS_TOKEN_KEY, token)
    }
  } else {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }
}

export function setRefreshToken(token) {
  if (token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, token)
  } else {
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }
}

export function setTokens({ access_token, refresh_token } = {}) {
  if (access_token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, access_token)
  } else {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
  }

  if (refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token)
  } else {
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

/** URL tuyệt đối cho các thẻ không qua fetch (vd: <video src={videoUrl(...)} />). */
export function apiUrl(path) {
  return `${BASE_URL}${path}`
}

function handleSessionExpired() {
  clearTokens()
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('janus:unauthorized'))
    if (
      window.location &&
      !window.location.pathname.startsWith('/login') &&
      !window.location.pathname.startsWith('/register')
    ) {
      window.location.href = '/login'
    }
  }
}

/**
 * Quản lý hàng đợi và tác vụ refresh token rotation:
 * - Khi có nhiều request đồng thời nhận 401, chỉ 1 request gọi POST /v1/auth/refresh.
 * - Toàn bộ các request còn lại xếp hàng đợi kết quả từ Promise duy nhất này (singleton).
 * - Nhận cặp token mới -> cập nhật localStorage và giải phóng hàng đợi.
 * - Nếu refresh thất bại -> xóa token, chuyển hướng về /login và báo lỗi.
 */
let refreshPromise = null

export async function rotateTokens() {
  if (refreshPromise) {
    return refreshPromise
  }

  const currentRefreshToken = getRefreshToken()
  if (!currentRefreshToken) {
    handleSessionExpired()
    throw new ApiError(401, 'Không có refresh token để làm mới phiên')
  }

  refreshPromise = (async () => {
    try {
      const response = await fetch(`${BASE_URL}/v1/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: currentRefreshToken }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => null)
        const detail = errorData?.detail || 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'
        throw new ApiError(response.status, detail)
      }

      const data = await response.json()
      if (!data?.access_token) {
        throw new ApiError(401, 'Dữ liệu phản hồi refresh token không hợp lệ')
      }

      setTokens({
        access_token: data.access_token,
        refresh_token: data.refresh_token || currentRefreshToken,
      })

      return data.access_token
    } catch (err) {
      handleSessionExpired()
      throw err
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

/**
 * Gọi API backend kèm Interceptor tự động refresh token rotation và retry khi 401.
 * @param {string} path    path tương đối, ví dụ "/v1/auth/login"
 * @param {object} options { method, body, auth, headers, signal, _retry }
 */
export async function apiFetch(path, options = {}) {
  const { method = 'GET', body, auth = true, headers = {}, signal, _retry = false } = options
  const token = getToken()

  const requestHeaders = { ...headers }
  const isFormData = body instanceof FormData
  if (body && !isFormData) requestHeaders['Content-Type'] = 'application/json'
  if (auth && token) requestHeaders.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: requestHeaders,
      body: body === undefined || body === null ? undefined : isFormData ? body : JSON.stringify(body),
      signal,
    })
  } catch {
    throw new ApiError(0, 'Không kết nối được tới máy chủ. Hãy kiểm tra backend đang chạy.')
  }

  // Response Interceptor: Tự động refresh token nếu nhận 401 Unauthorized
  const isAuthEndpoint =
    path.includes('/auth/login') ||
    path.includes('/auth/refresh') ||
    path.includes('/auth/password/reset') ||
    path.includes('/auth/password/forgot')

  if (response.status === 401 && auth && !isAuthEndpoint && !_retry) {
    const refreshToken = getRefreshToken()
    if (refreshToken) {
      try {
        const newAccessToken = await rotateTokens()
        // Retry request ban đầu với access token mới
        return await apiFetch(path, {
          ...options,
          headers: {
            ...headers,
            Authorization: `Bearer ${newAccessToken}`,
          },
          _retry: true,
        })
      } catch (refreshError) {
        throw refreshError instanceof ApiError
          ? refreshError
          : new ApiError(401, 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.')
      }
    } else {
      handleSessionExpired()
    }
  }

  if (response.status === 204) return null

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    let detail = null
    if (typeof payload?.detail === 'string') {
      detail = payload.detail
    } else if (Array.isArray(payload?.detail)) {
      // Lỗi xác thực Pydantic (ví dụ 422 email sai định dạng): detail là mảng.
      detail = payload.detail
        .map((e) => {
          const loc = e.loc ? e.loc.join('.') : ''
          const msg = e.msg || e.message || ''
          return loc ? `${loc}: ${msg}` : msg
        })
        .join('; ')
    }
    throw new ApiError(response.status, detail || `Yêu cầu thất bại (${response.status})`)
  }
  return payload
}
