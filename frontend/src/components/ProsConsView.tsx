import { Scale } from 'lucide-react'
import type { ProsConsEnrichment, ProConItem } from '../ideaWorkspace'

const MAX_ITEMS = 3
const RANK = { High: 0, Medium: 1, Low: 2 }

function topItems(items: ProConItem[]): ProConItem[] {
  // Stable sort keeps the discussion order within one impact level.
  return items
    .slice()
    .sort((a, b) => RANK[a.severity_or_impact] - RANK[b.severity_or_impact])
    .slice(0, MAX_ITEMS)
}

export function ProsConsView({ data }: { data?: ProsConsEnrichment | null }) {
  if (!data || (!data.pros?.length && !data.cons?.length && !data.summary)) return null

  const pros = topItems(data.pros)
  const cons = topItems(data.cons)

  return (
    <section className="pros-cons-panel" aria-label="Pros and Cons Analysis">
      <div className="panel-header">
        <div className="panel-title-group">
          <span className="panel-icon tone-blue" aria-hidden="true"><Scale size={18} /></span>
          <div><h3 className="panel-title">Pros &amp; cons</h3><p className="panel-subtitle">The top three of each, by impact.</p></div>
        </div>
      </div>

      {data.summary && <p className="panel-summary-narrative">{data.summary}</p>}

      <div className="pros-cons-columns">
        <div className="column-pane pros-column">
          <div className="column-header pros-heading"><span className="column-dot" /><h4>Pros</h4></div>
          <div className="cards-stack">
            {pros.map((pro, index) => {
              const impact = pro.severity_or_impact
              return <article key={index} className="argument-card pro-card">
                <div className="card-top-row"><span className="card-category">{pro.category}</span><span className={`impact-badge impact-${impact.toLowerCase()}`}>{impact} Impact</span></div>
                <p className="card-point">{pro.point}</p>
              </article>
            })}
            {pros.length === 0 && <p className="no-items-hint">No pros recorded yet.</p>}
          </div>
        </div>

        <div className="column-pane cons-column">
          <div className="column-header cons-heading"><span className="column-dot" /><h4>Cons</h4></div>
          <div className="cards-stack">
            {cons.map((con, index) => {
              const risk = con.severity_or_impact
              return <article key={index} className="argument-card con-card">
                <div className="card-top-row"><span className="card-category">{con.category}</span><span className={`risk-badge risk-${risk.toLowerCase()}`}>{risk} Risk</span></div>
                <p className="card-point">{con.point}</p>
              </article>
            })}
            {cons.length === 0 && <p className="no-items-hint">No cons recorded yet.</p>}
          </div>
        </div>
      </div>
    </section>
  )
}
