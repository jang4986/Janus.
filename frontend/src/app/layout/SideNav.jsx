import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import Icon from '@/shared/components/Icon'
import { useAuth } from '@/features/auth/AuthContext'



const NAV_ITEMS = [
  { to: '/', label: 'Dành cho bạn', icon: 'home', end: true },
  { to: '/moderation', label: 'Kiểm duyệt', icon: 'shield', roles: ['moderator'] },
  { to: '/admin', label: 'Quản trị', icon: 'user', roles: ['admin'] },
]

const SEARCH_HISTORY = ['video ngắn', 'kiểm duyệt', 'janus']

export default function SideNav() {
  const { user, isAuthenticated, logout } = useAuth()
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchText, setSearchText] = useState('')
  const navigate = useNavigate()

  function searchTag(value = searchText) {
    const tag = value.trim().replace(/^#/, '')
    if (!tag) return
    navigate(`/?description=${encodeURIComponent(tag)}`)
    setSearchText(tag)
    setSearchOpen(false)
  }

  return (
    <aside className="sidenav">
      <div className="brand-row">
        <NavLink to="/" className="brand">
          <span className="brand-mark">
            <Icon name="play" size={14} />
          </span>
          Janus
        </NavLink>
      </div>

      <div className="nav-search-wrap">
        <form className="nav-search" onSubmit={(event) => {event.preventDefault();searchTag()}}>
          <Icon name="search" size={16} />
          <input type="search" value={searchText} placeholder="Tìm video hoặc nhãn" onChange={(event)=>setSearchText(event.target.value)} onFocus={() => setSearchOpen(true)} onBlur={() => setTimeout(() => setSearchOpen(false), 150)} />
        </form>
        {searchOpen && (
          <div className="search-dropdown">
            <div className="search-section">
              <div className="search-section-title">Lịch sử tìm kiếm</div>
              {SEARCH_HISTORY.map((item) => (
                <button key={item} type="button" className="search-item" onMouseDown={(event)=>event.preventDefault()} onClick={()=>searchTag(item)}>
                  <Icon name="clock" size={14} />
                  <span>{item}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <nav className="side-nav" aria-label="Điều hướng chính">
        {NAV_ITEMS.filter((item) => {
          if (item.roles) return user && item.roles.includes(user.role)
          if (item.auth) return isAuthenticated
          return true
        }).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon name={item.icon} size={18} />
            <span>{item.label}</span>
          </NavLink>
        ))}
        {isAuthenticated && (
          <>
            <NavLink to="/upload" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Icon name="upload" size={18} />
              <span>Tải video</span>
            </NavLink>
            <NavLink to="/profile" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Icon name="user" size={18} />
              <span>Hồ sơ</span>
            </NavLink>
            <NavLink to="/bookmarks" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Icon name="bookmark" size={18} />
              <span>Video đã lưu</span>
            </NavLink>
          </>
        )}
      </nav>

      <div className="side-foot">
        {isAuthenticated ? (
          <>
            <div className="side-user">
              <span className="avatar">{user.avatar_url ? <img src={user.avatar_url} alt="" /> : user.display_name.slice(0, 2).toUpperCase()}</span>
              <div className="side-user-copy">
                <strong>{user.display_name}</strong>
                <span>#{user.discriminator}</span>
              </div>
            </div>
            <button type="button" className="nav-item" onClick={logout}>
              <Icon name="logout" size={18} />
              <span>Đăng xuất</span>
            </button>
          </>
        ) : null}
      </div>
    </aside>
  )
}
