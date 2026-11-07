import { apiFetch, setTokens } from '@/shared/api/client'

/**
 * Đăng nhập, trả về { access_token, token_type, refresh_token }.
 * Tự động đồng bộ cặp access_token và refresh_token vào storage.
 */
export async function login(email, password) {
  const session = await apiFetch('/v1/auth/login', {
    method: 'POST',
    body: { email, password },
    auth: false,
  })
  if (session?.access_token) {
    setTokens({
      access_token: session.access_token,
      refresh_token: session.refresh_token,
    })
  }
  return session
}

/** Đăng ký, trả về hồ sơ người dùng vừa tạo. */
export function register({ email, displayName, password }) {
  return apiFetch('/v1/auth/register', {
    method: 'POST',
    body: { email, display_name: displayName, password },
    auth: false,
  })
}

/** Làm mới phiên làm việc bằng refresh token (xoay vòng token). */
export function refreshSession(refreshToken) {
  return apiFetch('/v1/auth/refresh', {
    method: 'POST',
    body: { refresh_token: refreshToken },
    auth: false,
  })
}

/**
 * Đăng xuất: gửi Bearer access token (JTI blacklist) và refresh token (thu hồi).
 */
export function logout(refreshToken) {
  return apiFetch('/v1/auth/logout', {
    method: 'POST',
    body: refreshToken ? { refresh_token: refreshToken } : undefined,
    auth: true,
  })
}

/** Quên mật khẩu: gửi email yêu cầu đặt lại mật khẩu. */
export function forgotPassword(email) {
  return apiFetch('/v1/auth/password/forgot', {
    method: 'POST',
    body: { email },
    auth: false,
  })
}

/** Đặt lại mật khẩu mới bằng token. */
export function resetPassword(token, newPassword) {
  return apiFetch('/v1/auth/password/reset', {
    method: 'POST',
    body: { token, new_password: newPassword },
    auth: false,
  })
}

/** Lấy hồ sơ của token hiện tại — dùng để khôi phục phiên đăng nhập khi tải lại trang. */
export function fetchProfile() {
  return apiFetch('/v1/profile')
}

export function updateProfile(payload) {
  return apiFetch('/v1/profile', { method: 'PATCH', body: payload })
}
