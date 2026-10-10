import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'
import { Code, Eye } from 'lucide-react'

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  themeVariables: {
    darkMode: true,
    background: '#0b1120',
    primaryColor: '#3b82f6',
    primaryTextColor: '#f1f5f9',
    primaryBorderColor: '#60a5fa',
    lineColor: '#94a3b8',
    secondaryColor: '#8b5cf6',
    tertiaryColor: '#1e293b',
    fontFamily: 'Inter, system-ui, sans-serif',
  },
})

export function MermaidDiagram({ code, idPrefix = 'mermaid' }: { code?: string | null; idPrefix?: string }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    let isMounted = true
    const renderDiagram = async () => {
      if (!code?.trim()) {
        setSvg('')
        setError(null)
        return
      }
      try {
        const id = `${idPrefix}-${Math.random().toString(36).substring(2, 9)}`
        const result = await mermaid.render(id, code.trim())
        if (isMounted) {
          setSvg(result.svg)
          setError(null)
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err?.message || 'Failed to render diagram')
        }
      }
    }
    renderDiagram()
    return () => {
      isMounted = false
    }
  }, [code, idPrefix])

  if (!code?.trim()) return null

  return (
    <div className="mermaid-container">
      <div className="mermaid-header-bar">
        <span className="diagram-type-tag">Mermaid Flowchart</span>
        <button
          type="button"
          className="code-toggle-btn"
          onClick={() => setShowRaw(!showRaw)}
          title={showRaw ? 'Switch to visual diagram' : 'View mermaid source syntax'}
        >
          {showRaw ? <><Eye size={13} /> Visual Diagram</> : <><Code size={13} /> Mermaid Syntax</>}
        </button>
      </div>

      {showRaw ? (
        <pre className="diagram-raw-pre">
          <code>{code}</code>
        </pre>
      ) : error ? (
        <div className="diagram-fallback">
          <p className="diagram-error-hint">Rendering fallback (syntax view):</p>
          <pre className="diagram-raw-pre">
            <code>{code}</code>
          </pre>
        </div>
      ) : (
        <div
          ref={containerRef}
          className="mermaid-rendered-svg"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      )}
    </div>
  )
}
