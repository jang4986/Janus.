import Icon from '@/shared/components/Icon'
import { ErrorNote, Spinner } from '@/shared/components/Feedback'
import { useAuth } from '@/features/auth/AuthContext'
import { useAiAnalysis } from '../hooks/useAiAnalysis'

/**
 * Phân tích và cấu trúc hóa chuỗi log / transcript từ pipeline AI.
 * Loại bỏ thông tin đường dẫn nội bộ và bóc tách thành các module trực quan.
 */
function parseTranscript(text, includeDiagnostics) {
  if (!text) return []
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean)
  const items = []
  const pendingModules = []

  for (const line of lines) {
    // Loại bỏ đường dẫn thư mục nội bộ debug (vd: model sẽ đặt tại E:\PBL6\...)
    const clean = line
      .replace(/\s*\(model\s+sẽ\s+đặt\s+tại\s+[^)]+\)/gi, '')
      .replace(/\s*\([a-zA-Z]:\\[^)]+\)/gi, '')
      .replace(/\s*\((\/[^)\s]+)+\)/gi, '')
      .trim()

    if (clean.startsWith('[NSFW-Detection chưa sẵn sàng:')) {
      continue
    } else if (clean.includes('[NSFW-Detection]') || clean.includes('phán quyết:')) {
      const decM = clean.match(/phán\s+quyết:\s*([A-Za-z0-9_]+)/i)
      const confM = clean.match(/độ\s+tin\s+cậy:\s*([0-9.]+)/i)
      const ancM = clean.match(/anchor\s+đã\s+đánh\s+giá:\s*(\d+)/i)
      const fpsM = clean.match(/fps:\s*([0-9.]+)/i)
      const decision = decM ? decM[1].toUpperCase() : 'UNKNOWN'
      const conf = confM ? Math.round(parseFloat(confM[1]) * 100) : null
      const anchors = ancM ? ancM[1] : null
      const fps = fpsM ? Math.round(parseFloat(fpsM[1])) : null

      items.push({
        type: 'nsfw',
        title: 'Thị giác / NSFW',
        decision,
        isAdult: decision === 'ADULT',
        confidence: conf,
        anchors,
        fps,
      })
    } else if (clean.includes('[Speech-to-Text]') || clean.includes('transcript âm thanh')) {
      const isPending = clean.includes('chưa được triển khai') || clean.includes('chưa có')
      if (isPending && !includeDiagnostics) continue
      const content = clean.replace(/^\[Speech-to-Text\]\s*/i, '').trim()
      items.push({
        type: 'stt',
        title: 'Bản chép lời / STT',
        isPending,
        content: isPending ? 'Chưa có bản chép lời âm thanh (tính năng đang phát triển)' : content,
      })
    } else if (clean.includes('[Chưa triển khai]')) {
      if (!includeDiagnostics) continue
      const modM = clean.match(/^\[Chưa triển khai\]\s*([^:]+):\s*(.*)/i)
      if (modM) {
        pendingModules.push({
          key: modM[1].trim(),
          name: modM[1].trim().toUpperCase(),
          desc: modM[2].trim(),
        })
      }
    } else {
      if (!includeDiagnostics) continue
      items.push({
        type: 'general',
        title: 'Thông tin hệ thống',
        content: clean,
      })
    }
  }

  if (pendingModules.length > 0) {
    items.push({
      type: 'pending_modules',
      title: 'Các module mở rộng',
      modules: pendingModules,
    })
  }

  return items
}

function FormattedTranscript({ transcript, includeDiagnostics }) {
  if (!transcript) {
    return <p className="ai-transcript-empty">Không có bản chép lời hoặc chi tiết phân tích cho video này.</p>
  }

  const items = parseTranscript(transcript, includeDiagnostics)

  if (items.length === 0) {
    return <p className="ai-transcript-empty">Không có thông tin phân tích khả dụng.</p>
  }

  return (
    <ul className="ai-analysis-list">
      {items.map((item, idx) => {
        if (item.type === 'nsfw') {
          return (
            <li key={idx} className="ai-analysis-item nsfw-item">
              <span className="ai-bullet-icon ai-bullet-eye">
                <Icon name="eye" size={14} />
              </span>
              <div className="ai-analysis-body">
                <div className="ai-analysis-header">
                  <strong className="ai-analysis-name">Thị giác / NSFW</strong>
                  <span className={`ai-decision-tag ${item.isAdult ? 'tag-danger' : 'tag-success'}`}>
                    {item.decision}
                  </span>
                </div>
                <div className="ai-analysis-details">
                  {item.confidence !== null && (
                    <span className="ai-meta-point">
                      Độ tin cậy: <strong>{item.confidence}%</strong>
                    </span>
                  )}
                </div>
              </div>
            </li>
          )
        }

        if (item.type === 'stt') {
          return (
            <li key={idx} className="ai-analysis-item stt-item">
              <span className="ai-bullet-icon">
                <Icon name="volume" size={14} />
              </span>
              <div className="ai-analysis-body">
                <div className="ai-analysis-header">
                  <strong className="ai-analysis-name">Bản chép lời / STT</strong>
                </div>
                {item.isPending ? (
                  <p className="ai-text-muted">{item.content}</p>
                ) : (
                  <p className="ai-stt-content">“{item.content}”</p>
                )}
              </div>
            </li>
          )
        }

        if (item.type === 'pending_modules') {
          return (
            <li key={idx} className="ai-analysis-item modules-item ai-muted-item">
              <span className="ai-bullet-icon">
                <Icon name="shield" size={14} />
              </span>
              <div className="ai-analysis-body">
                <div className="ai-analysis-header">
                  <strong className="ai-analysis-name">Các module mở rộng</strong>
                </div>
                <div className="ai-modules-chips">
                  {item.modules.map((m) => (
                    <span key={m.key} className="ai-chip-pending">
                      <span className="dot-indicator" />
                      <strong>{m.name}</strong>: <em>Chưa triển khai</em>
                    </span>
                  ))}
                </div>
              </div>
            </li>
          )
        }

        return (
          <li key={idx} className="ai-analysis-item general-item">
            <span className="ai-bullet-icon">
              <Icon name="spark" size={14} />
            </span>
            <div className="ai-analysis-body">
              <p className="ai-general-content">{item.content}</p>
            </div>
          </li>
        )
      })}
    </ul>
  )
}

/**
 * Hiển thị kết quả phân tích THẬT từ GET /v1/videos/{id}/ai.
 * Panel tự poll cho tới khi job kết thúc (backend chạy job nền).
 */
export default function AiResultPanel({ videoId, result: propResult, loading: propLoading }) {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const internal = useAiAnalysis(!propResult ? videoId : null)
  const result = propResult !== undefined ? propResult : internal.result
  const loading = propLoading !== undefined ? propLoading : internal.loading
  const error = internal.error
  const detectorIssue = result?.error_message || result?.transcript?.split(/\r?\n/).find((line) => line.startsWith('[NSFW-Detection chưa sẵn sàng:'))
  const modelLabel = result?.labels?.find((l) => l.type === 'nsfw') ?? result?.labels?.[0]
  const modelName = modelLabel?.name || 'Trạng thái AI'
  const isTestResult = /Mock transcript for development testing|NSFW-Detection chưa sẵn sàng/i.test(
    `${result?.transcript || ''}\n${result?.error_message || ''}`,
  )

  if (!videoId) return null
  // Kết quả mô phỏng và lỗi chẩn đoán chỉ hiển thị trong giao diện quản trị.
  if (!isAdmin && isTestResult) return null

  return (
    <section className="ai-panel" aria-live="polite">
      <header className="ai-head">
        <div>
          <h2>Kết quả phân tích</h2>
        </div>
        <span className={`ai-state ${result?.job_status === 'succeeded' ? 'ok' : ''}`}>
          {loading && <Spinner label="Đang chờ kết quả" />}
          {modelName}
        </span>
      </header>

      {error && (isAdmin
        ? <ErrorNote>{error}</ErrorNote>
        : <p className="ai-user-error" role="status">Chưa thể tải kết quả phân tích lúc này. Vui lòng thử lại sau.</p>)}

      {result && (
        <>
          {isAdmin && (result.job_status === 'failed' || detectorIssue) && (
            <div className="ai-result-warning" role="alert">
              <strong>{result.job_status === 'failed' ? 'Phân tích video thất bại' : 'Chưa thể chạy model kiểm duyệt'}</strong>
              {result.job_status === 'succeeded' && <span>Kết quả bên dưới là dữ liệu mô phỏng, chưa được model thực phân tích.</span>}
              <span>{detectorIssue?.replace(/^\[NSFW-Detection chưa sẵn sàng:\s*/i, '').replace(/\]$/, '') || 'Không nhận được kết quả phân tích từ hệ thống.'}</span>
            </div>
          )}
          {!isAdmin && result.job_status === 'failed' && (
            <p className="ai-user-error" role="status">Chưa thể phân tích video lúc này.</p>
          )}
          <div className="ai-labels">
            {result.labels.length === 0 && <p className="ai-empty">Chưa có nhãn nào được gán cho video này.</p>}
            {result.labels.map((label) => (
              <div className="ai-label" key={label.name}>
                <div className="ai-label-top">
                  <strong>{label.name}</strong>
                  <span className={`level level-${label.level.toLowerCase()}`}>{label.level}</span>
                </div>
                <div className="ai-bar">
                  <i style={{ width: `${Math.round(label.confidence * 100)}%` }} />
                </div>
                <span className="ai-score">{Math.round(label.confidence * 100)}% độ tin cậy</span>
              </div>
            ))}
          </div>

          <div className="ai-transcript">
            <span className="ai-transcript-title">
              <Icon name="spark" size={13} /> CHI TIẾT PHÂN TÍCH & BẢN CHÉP LỜI
            </span>
            <FormattedTranscript transcript={result.transcript} includeDiagnostics={isAdmin} />
          </div>
        </>
      )}
    </section>
  )
}
