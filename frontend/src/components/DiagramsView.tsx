import { useState } from 'react'
import { GitBranch, Network, CheckSquare, Layers, Image as ImageIcon } from 'lucide-react'
import type { WorkflowEnrichment, ArchitectureEnrichment } from '../ideaWorkspace'
import { MermaidDiagram } from './MermaidDiagram'

export function DiagramsView({
  workflow,
  systemGraph,
  ideaId,
}: {
  workflow?: WorkflowEnrichment | null
  systemGraph?: ArchitectureEnrichment | null
  ideaId?: string
}) {
  const [activeTab, setActiveTab] = useState<'workflow' | 'architecture'>('workflow')
  const [viewMode, setViewMode] = useState<'diagram' | 'svg'>('diagram')

  const hasWorkflow = Boolean(workflow && (workflow.steps?.length || workflow.mermaid_code || workflow.summary))
  const hasArchitecture = Boolean(
    systemGraph && (systemGraph.nodes?.length || systemGraph.mermaid_code || systemGraph.summary)
  )

  if (!hasWorkflow && !hasArchitecture) return null

  // Artifact URLs exposed by backend
  const cleanId = ideaId?.replace(/^engine-/, '')
  const workflowSvgUrl = `/enrichment/ideas/${cleanId}/artifacts/workflow.svg`
  const architectureSvgUrl = `/enrichment/ideas/${cleanId}/artifacts/system-architecture.svg`

  return (
    <section className="diagrams-panel" aria-label="System Diagrams and Workflow">
      {/* Panel Top Navigation */}
      <div className="diagrams-header-bar">
        <div className="diagrams-title-group">
          <GitBranch size={17} className="diagrams-icon" />
          <h3 className="panel-title">Visual Process Flow &amp; System Architecture</h3>
        </div>

        {/* Tab Switcher */}
        <div className="diagram-tabs" role="tablist">
          {hasWorkflow && (
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'workflow'}
              className={`diagram-tab-btn ${activeTab === 'workflow' ? 'active' : ''}`}
              onClick={() => setActiveTab('workflow')}
            >
              <GitBranch size={14} />
              <span>Process Workflow</span>
            </button>
          )}

          {hasArchitecture && (
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'architecture'}
              className={`diagram-tab-btn ${activeTab === 'architecture' ? 'active' : ''}`}
              onClick={() => setActiveTab('architecture')}
            >
              <Network size={14} />
              <span>System Architecture</span>
            </button>
          )}
        </div>
      </div>

      {/* Workflow Section */}
      {activeTab === 'workflow' && workflow && (
        <div className="diagram-content-container">
          {workflow.summary && (
            <p className="panel-summary-narrative">{workflow.summary}</p>
          )}

          {/* Stepper overview */}
          {Boolean(workflow.steps?.length) && (
            <div className="workflow-stepper">
              <span className="stepper-title">
                <CheckSquare size={14} />
                <span>Execution Steps ({workflow.steps?.length} stages)</span>
              </span>
              <div className="steps-list">
                {workflow.steps?.map((step, idx) => (
                  <div key={idx} className="step-row">
                    <span className="step-number">{idx + 1}</span>
                    <span className="step-text">{step}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* View Toggle (Mermaid vs SVG Image) */}
          <div className="diagram-subview-toggle">
            <button
              type="button"
              className={`subview-btn ${viewMode === 'diagram' ? 'active' : ''}`}
              onClick={() => setViewMode('diagram')}
            >
              <Layers size={13} /> Interactive Flowchart
            </button>
            <button
              type="button"
              className={`subview-btn ${viewMode === 'svg' ? 'active' : ''}`}
              onClick={() => setViewMode('svg')}
            >
              <ImageIcon size={13} /> Rendered SVG Vector
            </button>
          </div>

          {viewMode === 'diagram' && workflow.mermaid_code ? (
            <MermaidDiagram code={workflow.mermaid_code} idPrefix={`wf-${cleanId}`} />
          ) : (
            <div className="svg-illustration-wrapper">
              <img
                src={workflowSvgUrl}
                alt="Workflow SVG Vector Diagram"
                className="diagram-svg-img"
                onError={(e) => {
                  // If backend SVG is missing, fall back to showing mermaid
                  (e.target as HTMLElement).style.display = 'none'
                  setViewMode('diagram')
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* System Architecture Section */}
      {activeTab === 'architecture' && systemGraph && (
        <div className="diagram-content-container">
          {systemGraph.summary && (
            <p className="panel-summary-narrative">{systemGraph.summary}</p>
          )}

          {/* Architecture Components Cards */}
          {Boolean(systemGraph.nodes?.length) && (
            <div className="nodes-overview">
              <span className="stepper-title">
                <Layers size={14} />
                <span>Architectural Components ({systemGraph.nodes?.length} Modules)</span>
              </span>
              <div className="nodes-grid">
                {systemGraph.nodes?.map((node) => (
                  <div key={node.id} className="component-node-card">
                    <div className="node-card-top">
                      <strong className="node-label">{node.label}</strong>
                      <span className={`node-type-badge type-${node.component_type || 'service'}`}>
                        {node.component_type || 'service'}
                      </span>
                    </div>
                    {node.description && (
                      <p className="node-desc">{node.description}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* View Toggle */}
          <div className="diagram-subview-toggle">
            <button
              type="button"
              className={`subview-btn ${viewMode === 'diagram' ? 'active' : ''}`}
              onClick={() => setViewMode('diagram')}
            >
              <Layers size={13} /> Interactive Topology
            </button>
            <button
              type="button"
              className={`subview-btn ${viewMode === 'svg' ? 'active' : ''}`}
              onClick={() => setViewMode('svg')}
            >
              <ImageIcon size={13} /> Rendered SVG Vector
            </button>
          </div>

          {viewMode === 'diagram' && systemGraph.mermaid_code ? (
            <MermaidDiagram code={systemGraph.mermaid_code} idPrefix={`arch-${cleanId}`} />
          ) : (
            <div className="svg-illustration-wrapper">
              <img
                src={architectureSvgUrl}
                alt="System Architecture SVG Vector"
                className="diagram-svg-img"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none'
                  setViewMode('diagram')
                }}
              />
            </div>
          )}
        </div>
      )}
    </section>
  )
}
