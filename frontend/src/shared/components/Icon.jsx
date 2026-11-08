/** Bộ icon SVG nội bộ — tránh thêm dependency chỉ để dùng vài biểu tượng. */

const PATHS = {
  home: 'M3 10.5 12 3l9 7.5M5.5 9.5V20h13V9.5M9.5 20v-6h5v6',
  upload: 'M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-8 8a8 8 0 0 1 16 0',
  shield: 'M12 3 5 6v5.5c0 4 2.9 7.6 7 9.5 4.1-1.9 7-5.5 7-9.5V6l-7-3Zm-3 9 2.2 2.2L15 10',
  play: 'M8 5.5c0-.8.9-1.3 1.6-.8l8.6 5.2a1.9 1.9 0 0 1 0 3.3l-8.6 5.2c-.7.4-1.6 0-1.6-.8V5.5Z',
  pause: 'M9 5v14M15 5v14',
  flag: 'M5 21V4m0 0h11l-2 3.5L16 11H5',
  trash: 'M4 7h16M9 7V4.5h6V7m-8 0 1 13h8l1-13',
  check: 'm5 12.5 4.5 4.5L19 7',
  x: 'M6 6l12 12M18 6 6 18',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13.5V12l3.5 2',
  film: 'M4 4h16v16H4V4Zm4 0v16M16 4v16M4 9h4m8 0h4M4 15h4m8 0h4',
  spark: 'm12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Z',
  volume: 'M11 5 6.5 9H3v6h3.5L11 19V5Zm4.5 3.5a5 5 0 0 1 0 7M18 6a8 8 0 0 1 0 12',
  mute: 'M11 5 6.5 9H3v6h3.5L11 19V5Zm5 4 4 6m0-6-4 6',
  logout: 'M15 5V4a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-1m3-9-4 4m4-4-4-4m4 4H9',
  refresh: 'M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4',
  eye: 'M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Zm9.5 2.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-5.2-5.2',
  heart: 'M12 21s-7-4.6-9.3-8.7C1 9.2 2.5 5.5 6.2 4.6c2.1-.5 4.2.4 5.8 1.9 1.6-1.5 3.7-2.4 5.8-1.9 3.7.9 5.2 4.6 3.5 7.7C19 16.4 12 21 12 21Z',
  'heart-filled': 'M12 21s-7-4.6-9.3-8.7C1 9.2 2.5 5.5 6.2 4.6c2.1-.5 4.2.4 5.8 1.9 1.6-1.5 3.7-2.4 5.8-1.9 3.7.9 5.2 4.6 3.5 7.7C19 16.4 12 21 12 21Z',
  message: 'M21 15a4 4 0 0 1-4 4H7l-4 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8Z',
  bookmark: 'M6 4h12v17l-6-4-6 4V4Z',
  edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4 11.5-11.5Z',
  expand: 'M15 3h6v6 M21 3l-7 7 M9 21H3v-6 M3 21l7-7 M21 15v6h-6 M21 21l-7-7 M3 9V3h6 M3 3l7 7',
}

const FILLED = new Set(['heart-filled'])

export default function Icon({ name, size = 20, className = '' }) {
  const d = PATHS[name]
  if (!d) return null
  const isFilled = FILLED.has(name)
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={isFilled ? '#fe2c55' : 'none'}
      stroke={isFilled ? '#fe2c55' : 'currentColor'}
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  )
}
