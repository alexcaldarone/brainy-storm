import { Search } from 'lucide-react'
import type { CompetitorEnrichment } from '../ideaWorkspace'

export function CompetitorsView({ data }: { data?: CompetitorEnrichment | null }) {
  if (!data || (!data.competitors?.length && !data.market_landscape)) {
    return null
  }

  const landscape = data.market_landscape
  const competitors = data.competitors

  return (
    <section className="competitors-panel" aria-label="Competitor Analysis">
      <div className="panel-header">
        <div className="panel-title-group">
          <span className="panel-icon tone-orange" aria-hidden="true"><Search size={18} /></span>
          <div><h3 className="panel-title">Competitors</h3><p className="panel-subtitle">Found with live Google Search.</p></div>
        </div>
      </div>

      {landscape && <p className="panel-summary-narrative competitors-landscape">{landscape}</p>}

      {competitors.length > 0 && (
        <ul className="competitor-list">
          {competitors.map((comp, idx) => {
            const overview = comp.summary
            const difference = comp.differentiator
            return (
              <li key={idx} className="competitor-row">
                <div className="competitor-identity">
                  <h4 className="competitor-name">{comp.name}</h4>
                </div>
                <div className="competitor-copy">
                  {overview && <p className="competitor-overview">{overview}</p>}
                  {difference && <p className="competitor-difference"><span>We differ</span>{difference}</p>}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
