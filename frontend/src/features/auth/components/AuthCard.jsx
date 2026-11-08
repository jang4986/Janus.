import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import Icon from '@/shared/components/Icon'
import { ErrorNote } from '@/shared/components/Feedback'
import { useAuth } from '../AuthContext'

/**
 * Thẻ đăng nhập / đăng ký dùng chung.
 * mode="login"  → email + mật khẩu
 * mode="register" → thêm họ tên
 */
export default function AuthCard({ mode }) {
  const isRegister = mode === 'register'
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ email: '', password: '', displayName: '' })
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  const from = location.state?.from || '/'

  function update(field) {
    return (event) => setForm((current) => ({ ...current, [field]: event.target.value }))
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    if (isRegister && form.displayName.trim().length < 1) {
      setError('Vui lòng nhập họ tên hiển thị.')
      return
    }
    if (form.password.length < 8) {
      setError('Mật khẩu cần ít nhất 8 ký tự.')
      return
    }
    setSending(true)
    try {
      if (isRegister) {
        await register({ email: form.email, displayName: form.displayName.trim(), password: form.password })
      } else {
        await login(form.email, form.password)
      }
      navigate(from, { replace: true })
    } catch (requestError) {
      setError(requestError.detail || requestError.message)
      setSending(false)
    }
  }

  return (
    <div className="auth-card">
      <button type="button" className="auth-back" onClick={() => navigate('/')} aria-label="Quay lại">
        <Icon name="arrow" size={18} style={{ transform: 'rotate(180deg)' }} />
        <span>Quay lại</span>
      </button>

      <Link to="/" className="brand auth-brand">
        <span className="brand-mark">
          <Icon name="play" size={14} />
        </span>
        Janus
      </Link>

      <h1>{isRegister ? 'Tạo tài khoản' : 'Đăng nhập'}</h1>
      <p className="auth-sub">
        {isRegister
          ? 'Tạo tài khoản để tải video và theo dõi kết quả kiểm duyệt.'
          : 'Đăng nhập để tải video lên Janus.'}
      </p>

      <form className="auth-form" onSubmit={submit} noValidate>
        {isRegister && (
          <label className="field">
            <span>Username</span>
            <input
              className="text-input"
              value={form.displayName}
              onChange={update('displayName')}
              maxLength={120}
              required
              autoComplete="name"
              placeholder="Nguyễn Văn A"
            />
          </label>
        )}

        <label className="field">
          <span>Email</span>
          <input
            className="text-input"
            type="email"
            value={form.email}
            onChange={update('email')}
            required
            autoComplete="email"
            placeholder="ban@example.com"
          />
        </label>

        <label className="field">
          <span>Mật khẩu</span>
          <input
            className="text-input"
            type="password"
            value={form.password}
            onChange={update('password')}
            required
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            placeholder="Tối thiểu 8 ký tự"
          />
        </label>

        <ErrorNote>{error}</ErrorNote>

        <button type="submit" className="button primary block" disabled={sending}>
          {sending ? 'Đang xử lý…' : isRegister ? 'Đăng ký' : 'Đăng nhập'}
        </button>
      </form>

      <p className="auth-switch">
        {isRegister ? (
          <>
            Đã có tài khoản? <Link to="/login">Đăng nhập</Link>
          </>
        ) : (
          <>
            Chưa có tài khoản? <Link to="/register">Đăng ký</Link>
          </>
        )}
      </p>
    </div>
  )
}

