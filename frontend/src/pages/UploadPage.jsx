import { useState } from 'react'
import { Link } from 'react-router-dom'

import Icon from '@/shared/components/Icon'
import { ErrorNote, Spinner } from '@/shared/components/Feedback'
import AiResultPanel from '@/features/videos/components/AiResultPanel'
import UploadDropzone from '@/features/videos/components/UploadDropzone'
import { useVideoUpload } from '@/features/videos/hooks/useVideoUpload'
import { useAiAnalysis } from '@/features/videos/hooks/useAiAnalysis'

export default function UploadPage() {
  const [file, setFile] = useState(null)
  const [caption, setCaption] = useState('')
  const { status, progress, error, uploadedVideo, upload, reset: resetUpload } = useVideoUpload()
  const { result: aiResult, loading: aiLoading } = useAiAnalysis(uploadedVideo?.id)

  const uploading = status === 'uploading'
  const done = status === 'done'

  const isAiDone = aiResult?.job_status === 'succeeded' || aiResult?.job_status === 'failed'
  const isAiAnalyzing = done && !isAiDone
  const currentVideoStatus = aiResult?.video_status || uploadedVideo?.status

  function selectFile(nextFile) {
    reset()
    setFile(nextFile)
  }

  function reset() {
    resetUpload()
    setFile(null)
    setCaption('')
  }

  async function submit(event) {
    event.preventDefault()
    if (!file) return
    const captionValue = caption.trim()
    await upload(file, captionValue || null)
  }

  return (
    <main className="page upload-page">
      <header className="upload-heading">
        <div>
          <p>Chia sẻ một khoảnh khắc mới với cộng đồng Janus.</p>
        </div>
      </header>
      <div className="upload-grid">
        <form className="panel upload-panel" onSubmit={submit}>
          <UploadDropzone file={file} onSelect={selectFile} disabled={uploading} />

          <label className="field" htmlFor="caption">
            <span>
              Mô tả video <em>không bắt buộc</em>
            </span>
            <textarea
              id="caption"
              className="text-input"
              value={caption}
              maxLength={500}
              onChange={(event) => setCaption(event.target.value)}
              placeholder="Video này nói về điều gì?"
              disabled={uploading}
              style={{ height: '200px', resize: 'none', overflowY: 'auto' }}
            />
          </label>

          <ErrorNote>{error}</ErrorNote>

          {uploading && (
            <div className="upload-progress" aria-live="polite">
              <div className="progress-track">
                <i style={{ width: `${progress}%` }} />
              </div>
              <span>Đang tải lên {progress}%</span>
            </div>
          )}

          <div className="panel-actions">
            {done ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}>
                {isAiAnalyzing && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '10px 14px',
                      borderRadius: '8px',
                      background: 'rgba(255, 176, 32, 0.12)',
                      color: 'var(--warn)',
                      fontSize: '13px',
                    }}
                  >
                    <Spinner label="Đang phân tích AI" />
                    <span>Hệ thống AI đang phân tích và kiểm duyệt video…</span>
                  </div>
                )}

                {isAiDone && currentVideoStatus === 'rejected' && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '12px 14px',
                      borderRadius: '8px',
                      background: 'rgba(255, 92, 92, 0.12)',
                      border: '1px solid rgba(255, 92, 92, 0.3)',
                      color: 'var(--danger)',
                      fontSize: '13.5px',
                      fontWeight: 500,
                    }}
                  >
                    <Icon name="shield" size={17} />
                    <span>Video đã bị từ chối do vi phạm tiêu chuẩn cộng đồng</span>
                  </div>
                )}

                {isAiDone && (currentVideoStatus === 'pending_review' || currentVideoStatus === 'pending') && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '12px 14px',
                      borderRadius: '8px',
                      background: 'rgba(255, 176, 32, 0.12)',
                      border: '1px solid rgba(255, 176, 32, 0.3)',
                      color: 'var(--warn)',
                      fontSize: '13.5px',
                      fontWeight: 500,
                    }}
                  >
                    <Icon name="clock" size={17} />
                    <span>Video đang được lưu trữ và chờ kiểm duyệt viên xem xét thủ công</span>
                  </div>
                )}

                <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '4px' }}>
                  <button type="button" className="button ghost" onClick={reset}>
                    Tải video khác
                  </button>

                  {/* Khi đang upload hoặc AI đang phân tích: ẨN hoặc DISABLE nút 'Xem ở feed' */}
                  {isAiAnalyzing && (
                    <button type="button" className="button primary" disabled title="Đang phân tích kiểm duyệt...">
                      <span>Xem ở feed</span>
                      <Icon name="arrow" size={15} />
                    </button>
                  )}

                  {/* KHI ĐÃ CÓ KẾT QUẢ: Chỉ hiển thị nút 'Xem ở feed' khi status === 'published' */}
                  {isAiDone && currentVideoStatus === 'published' && (
                    <Link className="button primary" to="/">
                      Xem ở feed <Icon name="arrow" size={15} />
                    </Link>
                  )}
                </div>
              </div>
            ) : (
              <button type="submit" className="button primary" disabled={!file || uploading}>
                {uploading ? 'Đang tải lên…' : 'Tải lên và phân tích'}
              </button>
            )}
          </div>
        </form>

        <aside className="panel info-panel">
          <div className="info-title">
            <Icon name="shield" size={17} />
            <h2>Trước khi đăng</h2>
          </div>
          <ul className="info-list">
            <li>Chọn video MP4 có dung lượng dưới 50 MB.</li>
            <li>Thêm mô tả ngắn để mọi người hiểu nội dung.</li>
            <li>Video sẽ xuất hiện trên feed sau khi được duyệt.</li>
          </ul>
          <div className="upload-review-note"><span className="upload-review-dot" /><span>Video được kiểm tra an toàn trước khi xuất bản.</span></div>
        </aside>
      </div>

      {uploadedVideo && <AiResultPanel videoId={uploadedVideo.id} result={aiResult} loading={aiLoading} />}
    </main>
  )
}
