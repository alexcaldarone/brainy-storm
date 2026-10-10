import type { CSSProperties } from 'react'

/** Abstract artwork inspired by the brand's scalloped silhouettes. */
export function BrandShape({ variant }: { variant: number }) {
  const stacked = variant % 2 === 1
  return (
    <svg className={`brand-shape shape-${variant}`} viewBox="0 0 360 180" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <rect className="shape-ground" width="360" height="180" />
      {stacked ? <g className="shape-ink">
        <ellipse cx="180" cy="50" rx="108" ry="18" />
        <ellipse cx="180" cy="76" rx="130" ry="22" />
        <ellipse cx="180" cy="110" rx="153" ry="27" />
        <ellipse cx="180" cy="151" rx="178" ry="33" />
        <path d="M0 150h360v40H0z" />
      </g> : <path className="shape-ink" d="M-20 180V120Q12 30 44 130Q77-42 110 101Q145-97 180 76Q217-43 248 115Q278 9 310 137Q340 56 380 137V180Z" />}
    </svg>
  )
}

export function AbstractSymbol({ className = '' }: { className?: string }) {
  return <svg className={`abstract-symbol ${className}`} viewBox="0 0 40 40" aria-hidden="true" focusable="false">
    <path fill="currentColor" d="M2 34V23Q6 4 11 23Q15-9 21 19Q26 0 30 25Q35 11 38 28V34Z" />
  </svg>
}

export function RecordingShape({ active }: { active: boolean }) {
  return (
    <div className={`recording-visual ${active ? 'is-recording' : ''}`}>
      <svg viewBox="0 0 360 64" preserveAspectRatio="none" aria-hidden="true" focusable="false">
        <g className="recording-lobes">
          {Array.from({ length: 19 }, (_, index) => (
            <ellipse key={index} cx={10 + index * 19} cy="32" rx="12" ry={14 + ((index * 13) % 18)} style={{
              animationDelay: `${index * -0.19}s`, animationDuration: `${0.8 + ((index * 7) % 11) * 0.13}s`,
              '--sway': `${index % 2 ? 3 : -3}px`,
            } as CSSProperties} />
          ))}
        </g>
      </svg>
      <span>{active ? 'Listening' : 'Ready to record'}</span>
    </div>
  )
}
