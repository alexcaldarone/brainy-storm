import { Target, Sparkles } from 'lucide-react'

export function KeyConclusionCard({ conclusion }: { conclusion: string }) {
  return (
    <div className="key-conclusion-card" role="region" aria-label="Key Conclusion so Far">
      <div className="conclusion-header">
        <div className="conclusion-badge">
          <Target size={14} className="conclusion-icon" />
          <span>Key Conclusion so Far</span>
        </div>
        <span className="consensus-tag">
          <Sparkles size={12} />
          <span>Consensus Direction</span>
        </span>
      </div>
      <p className="conclusion-text">{conclusion}</p>
    </div>
  )
}
