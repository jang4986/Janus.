import { useState } from 'react'

import Icon from '@/shared/components/Icon'
import { EmptyState, ErrorNote, Spinner } from '@/shared/components/Feedback'
import { VIDEO_STATUS_LABEL, formatBytes, formatDateTime } from '@/shared/lib/format'
import {
  decideReport,
  decideVideo,
  fetchQueue,
  fetchReports,
} from '@/features/moderation/api/moderationApi'
import { useModerationList } from '@/features/moderation/hooks/useModerationList'
import { streamUrl } from '@/features/videos/api/videosApi'

const TABS = [
  { id: 'queue', label: 'Hàng đợi video' },
  { id: 'reports', label: 'Báo cáo' },
]

export default function ModerationPage() {
  const [tab, setTab] = useState('queue')
  const queue = useModerationList(fetchQueue)
  const reports = useModerationList(fetchReports)
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState('')

  const active = tab === 'queue' ? queue : reports

  async function decide(kind, id, action) {
    setBusyId(id)
    setError('')
    try {
      if (kind === 'queue') await decideVideo(id, action)
      else await decideReport(id, action)
      await Promise.all([queue.refresh(), reports.refresh()])
    } catch (requestError) {
      setError(requestError.detail || requestError.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <span className="overline">Trạng thái video xem xét</span>
          <h1>Hàng đợi kiểm duyệt</h1>
          <p className="page-sub">
            Duyệt, yêu cầu chỉnh sửa hoặc từ chối video trước khi xuất hiện trên feed.
          </p>
        </div>
        <div className="tabs" role="tablist">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              className={tab === item.id ? 'tab active' : 'tab'}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <ErrorNote>{error || active.error}</ErrorNote>

      {active.loading ? (
        <div className="page-center">
          <Spinner label="Đang tải danh sách" />
        </div>
      ) : active.items.length === 0 ? (
        <EmptyState
          icon="check"
          title={tab === 'queue' ? 'Không có video nào chờ duyệt' : 'Không có báo cáo đang mở'}
          hint="Mọi thứ đã được xử lý xong."
        />
      ) : tab === 'queue' ? (
        <ul className="mod-list">
          {active.items.map((video) => (
            <li className="mod-card" key={video.id}>
              <video className="mod-thumb" src={streamUrl(video.id)} controls playsInline preload="metadata" />
              <div className="mod-body">
                <div className="mod-title">
                  <strong>{video.caption || video.original_filename}</strong>
                  <span className="badge badge-warn">{VIDEO_STATUS_LABEL[video.status] || video.status}</span>
                </div>
                <p className="mod-meta">
                  @{video.owner_name || 'unknown'} · {formatBytes(video.size_bytes)} ·{' '}
                  {formatDateTime(video.created_at)}
                </p>
                <div className="mod-actions">
                  <button
                    type="button"
                    className="button primary"
                    disabled={busyId === video.id}
                    onClick={() => decide('queue', video.id, 'approve')}
                  >
                    <Icon name="check" size={15} /> Duyệt đăng
                  </button>
                  <button
                    type="button"
                    className="button ghost"
                    disabled={busyId === video.id}
                    onClick={() => decide('queue', video.id, 'reject')}
                  >
                    <Icon name="x" size={15} /> Từ chối
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="mod-list">
          {active.items.map((report) => (
            <li className="mod-card" key={report.id}>
              <div className="mod-body">
                <div className="mod-title">
                  <strong>Báo cáo video</strong>
                  <span className="badge badge-warn">Mở</span>
                </div>
                <p className="mod-reason">“{report.reason}”</p>
                <p className="mod-meta">Video: {report.video_caption || report.video_id}</p>
                <div className="mod-actions">
                  <button
                    type="button"
                    className="button primary"
                    disabled={busyId === report.id}
                    onClick={() => decide('reports', report.id, 'approve')}
                  >
                    <Icon name="flag" size={15} /> Xác nhận vi phạm
                  </button>
                  <button
                    type="button"
                    className="button ghost"
                    disabled={busyId === report.id}
                    onClick={() => decide('reports', report.id, 'reject')}
                  >
                    Bác bỏ báo cáo
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
