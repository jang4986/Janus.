import { Link, useLocation, useSearchParams } from 'react-router-dom'

import Icon from '@/shared/components/Icon'
import { useAuth } from '@/features/auth/AuthContext'

const TITLES = {
  '/': 'Dành cho bạn',
  '/upload': 'Tải video',
  '/profile': 'Hồ sơ của bạn',
  '/bookmarks': 'Video đã lưu',
  '/admin': 'Quản trị hệ thống',
  '/moderation': 'Hàng đợi kiểm duyệt',
  '/edit-video': 'Chỉnh sửa video',
}

export default function TopBar() {
  const { pathname } = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { user, isAuthenticated } = useAuth()
  const roleLabel = user?.role === 'moderator' ? 'Kiểm duyệt viên' : user?.role === 'admin' ? 'Quản trị viên' : null
  const feedView = searchParams.get('view') === 'grid' ? 'grid' : 'video'
  const showFeedSwitch = pathname === '/' && !searchParams.has('tag')

  function changeFeedView(nextView) {
    const nextParams = new URLSearchParams(searchParams)
    if (nextView === 'video') nextParams.delete('view')
    else nextParams.set('view', nextView)
    setSearchParams(nextParams, { replace: true })
  }

  return (
    <header className="topbar">
      <div className="topbar-title">
        <span className="crumb">Janus</span>
        <span className="crumb-sep">/</span>
        <strong>{TITLES[pathname] || 'Trang'}</strong>
      </div>

      <div className="topbar-actions">
        {isAuthenticated && roleLabel && (
          <span className="role-pill" title="Vai trò hiện tại">
            <i />
            {roleLabel}
          </span>
        )}
        {showFeedSwitch && (
          <div className="topbar-feed-switch" role="group" aria-label="Chế độ xem video">
            <button type="button" className={feedView === 'video' ? 'active' : ''} onClick={() => changeFeedView('video')} aria-pressed={feedView === 'video'}>Video dọc</button>
            <button type="button" className={feedView === 'grid' ? 'active' : ''} onClick={() => changeFeedView('grid')} aria-pressed={feedView === 'grid'}>Lưới</button>
          </div>
        )}
        {isAuthenticated ? null : (
          <Link to="/login" className="button ghost">
            Đăng nhập
          </Link>
        )}
      </div>
    </header>
  )
}
