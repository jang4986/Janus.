import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/features/auth/AuthContext'
import { RequireAuth, RequireRole } from './guards'
import MainLayout from './layout/MainLayout'
import FeedPage from '@/pages/FeedPage'
import LoginPage from '@/pages/LoginPage'
import ModerationPage from '@/pages/ModerationPage'
import ProfilePage from '@/pages/ProfilePage'
import RegisterPage from '@/pages/RegisterPage'
import UploadPage from '@/pages/UploadPage'
import EditVideoPage from '@/pages/EditVideoPage'
import AdminPage from '@/pages/AdminPage'
import BookmarksPage from '@/pages/BookmarksPage'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<MainLayout />}>
            <Route index element={<FeedPage />} />
            <Route
              path="upload"
              element={
                <RequireAuth>
                  <UploadPage />
                </RequireAuth>
              }
            />
            <Route
              path="edit-video"
              element={
                <RequireAuth>
                  <EditVideoPage />
                </RequireAuth>
              }
            />
            <Route
              path="profile"
              element={
                <RequireAuth>
                  <ProfilePage />
                </RequireAuth>
              }
            />
            <Route
              path="bookmarks"
              element={
                <RequireAuth>
                  <BookmarksPage />
                </RequireAuth>
              }
            />
            <Route
              path="moderation"
              element={
                <RequireRole roles={['moderator', 'admin']}>
                  <ModerationPage />
                </RequireRole>
              }
            />
            <Route
              path="admin"
              element={
                <RequireRole roles={['admin']}>
                  <AdminPage />
                </RequireRole>
              }
            />
          </Route>
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
