import { useState } from 'react'
import { TrendingUp, ShieldAlert, ChevronDown, ChevronUp, AlertTriangle, HelpCircle, CheckCircle2 } from 'lucide-react'
import type { ProsConsEnrichment, ProConItem } from '../ideaWorkspace'

export function ProsConsView({ data }: { data?: ProsConsEnrichment | null }) {
  const [showExtended, setShowExtended] = useState(false)

  if (!data || (!data.pros?.length && !data.cons?.length && !data.summary)) {
    return null
  }

  // Normalize pros & cons in case strings were passed
  const normalizeItem = (item: ProConItem | string): ProConItem => {
    if (typeof item === 'string') {
      return {
        point: item,
        category: 'Discussion',
        severity_or_impact: 'Medium',
        source_context: '',
      }
    }
    return item
  }

  const pros = (data.pros || []).map(normalizeItem)
  const cons = (data.cons || []).map(normalizeItem)
  const hasExtended = Boolean(
    data.key_risks?.length || data.assumptions?.length || data.open_questions?.length
  )

  return (
    <section className="pros-cons-panel" aria-label="Pros and Cons Analysis">
      {/* Header bar matching Image 1 */}
      <div className="panel-header">
        <div className="panel-title-group">
          <span className="panel-emoji-icon" aria-hidden="true">⚖️</span>
          <h3 className="panel-title">Pros &amp; Cons Identified from Body (Categorized &amp; Sorted)</h3>
        </div>
        <span className="panel-header-badge">Sorted by Impact</span>
      </div>

      {/* Narrative summary of the debate */}
      {data.summary && (
        <p className="panel-summary-narrative">{data.summary}</p>
      )}

      {/* Two-column Pros & Cons Grid */}
      <div className="pros-cons-columns">
        {/* Pros Column */}
        <div className="column-pane pros-column">
          <div className="column-header pros-heading">
            <TrendingUp size={16} className="column-icon" />
            <h4>Pros Voiced in Discussion</h4>
          </div>

          <div className="cards-stack">
            {pros.map((pro, idx) => {
              const impact = pro.severity_or_impact || 'Medium'
              return (
                <div key={idx} className="argument-card pro-card">
                  <div className="card-top-row">
                    <span className="card-category">{pro.category || 'General'}</span>
                    <span className={`impact-badge impact-${impact.toLowerCase()}`}>
                      {impact} Impact
                    </span>
                  </div>
                  <p className="card-point">{pro.point}</p>
                  {pro.source_context && (
                    <blockquote className="card-quote">
                      &ldquo;{pro.source_context.replace(/^["“”]|["“”]$/g, '').trim()}&rdquo;
                    </blockquote>
                  )}
                </div>
              )
            })}
            {pros.length === 0 && <p className="no-items-hint">No pros recorded yet.</p>}
          </div>
        </div>

        {/* Cons Column */}
        <div className="column-pane cons-column">
          <div className="column-header cons-heading">
            <ShieldAlert size={16} className="column-icon" />
            <h4>Cons Voiced in Discussion</h4>
          </div>

          <div className="cards-stack">
            {cons.map((con, idx) => {
              const risk = con.severity_or_impact || 'Medium'
              return (
                <div key={idx} className="argument-card con-card">
                  <div className="card-top-row">
                    <span className="card-category">{con.category || 'General'}</span>
                    <span className={`risk-badge risk-${risk.toLowerCase()}`}>
                      {risk} Risk
                    </span>
                  </div>
                  <p className="card-point">{con.point}</p>
                  {con.source_context && (
                    <blockquote className="card-quote">
                      &ldquo;{con.source_context.replace(/^["“”]|["“”]$/g, '').trim()}&rdquo;
                    </blockquote>
                  )}
                </div>
              )
            })}
            {cons.length === 0 && <p className="no-items-hint">No cons recorded yet.</p>}
          </div>
        </div>
      </div>

      {/* Extended Context: Key Risks, Assumptions & Open Questions */}
      {hasExtended && (
        <div className="extended-governance-section">
          <button
            type="button"
            className="extended-toggle-button"
            onClick={() => setShowExtended(!showExtended)}
          >
            <span>Governance &amp; Feasibility Context ({[
              data.key_risks?.length ? `${data.key_risks.length} Risks` : null,
              data.assumptions?.length ? `${data.assumptions.length} Assumptions` : null,
              data.open_questions?.length ? `${data.open_questions.length} Open Questions` : null,
            ].filter(Boolean).join(' · ')})</span>
            {showExtended ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>

          {showExtended && (
            <div className="extended-grid">
              {Boolean(data.key_risks?.length) && (
                <div className="extended-card risks-card">
                  <h5><AlertTriangle size={14} /> Key Risks</h5>
                  <ul>
                    {data.key_risks?.map((risk, i) => <li key={i}>{risk}</li>)}
                  </ul>
                </div>
              )}
              {Boolean(data.assumptions?.length) && (
                <div className="extended-card assumptions-card">
                  <h5><CheckCircle2 size={14} /> Core Assumptions</h5>
                  <ul>
                    {data.assumptions?.map((item, i) => <li key={i}>{item}</li>)}
                  </ul>
                </div>
              )}
              {Boolean(data.open_questions?.length) && (
                <div className="extended-card questions-card">
                  <h5><HelpCircle size={14} /> Open Questions</h5>
                  <ul>
                    {data.open_questions?.map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
