import { useLayoutEffect, useRef } from 'react'
import type { Idea } from './ideaWorkspace'
import { AbstractSymbol } from './BrandShape'
import { KeyConclusionCard } from './components/KeyConclusionCard'
import { ProsConsView } from './components/ProsConsView'
import { CompetitorsView } from './components/CompetitorsView'
import { EnrichedJsonView } from './components/EnrichedJsonView'

function TextBlock({
  value,
  label,
  className,
  placeholder,
  onChange,
  singleLine = false,
}: {
  value: string
  label: string
  className: string
  placeholder: string
  onChange: (value: string) => void
  singleLine?: boolean
}) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const input = ref.current
    if (!input) return
    const resize = () => {
      input.style.height = '0px'
      input.style.height = `${input.scrollHeight}px`
    }
    resize()
    const observer = new ResizeObserver(resize)
    if (input.parentElement) observer.observe(input.parentElement)
    return () => observer.disconnect()
  }, [value])

  return (
    <textarea
      ref={ref}
      rows={1}
      aria-label={label}
      className={`editable-block ${className}`}
      value={value}
      placeholder={placeholder}
      onChange={(event) =>
        onChange(singleLine ? event.target.value.replace(/[\r\n]+/g, ' ') : event.target.value)
      }
      onKeyDown={(event) => {
        if (singleLine && event.key === 'Enter') {
          event.preventDefault()
          event.currentTarget.blur()
        }
      }}
    />
  )
}

export function EditableIdea({
  idea,
  onChange,
  storageError,
}: {
  idea: Idea
  onChange: (fields: Partial<Pick<Idea, 'title' | 'summary' | 'tag'>>) => void
  storageError: boolean
}) {
  const keyConclusion = idea.conclusion || idea.pros_cons?.summary

  return (
    <div className="enriched-idea-container">
      <div className="idea-intro">
        <div className="idea-header-block">
          <AbstractSymbol className="idea-page-symbol" />
          <div className="idea-meta-badges">
            {idea.votes !== undefined && idea.votes > 0 && (
              <span className="votes-pill">
                ★ {idea.votes} {idea.votes === 1 ? 'vote' : 'votes'}
              </span>
            )}
          </div>
        </div>
        <div className="idea-editor-title" role="heading" aria-level={1}>
          <TextBlock
            label="Idea title"
            className="editable-title"
            value={idea.title}
            placeholder="Untitled idea"
            singleLine
            onChange={(title) => onChange({ title })}
          />
        </div>
        <div className="idea-tag-row">
          <input
            className="editable-tag idea-tag"
            aria-label="Idea tag"
            value={idea.tag}
            placeholder="Add a tag"
            onChange={(event) => onChange({ tag: event.target.value })}
          />
        </div>
        <div className="idea-summary-section">
          <label className="section-eyebrow-label">Executive Summary</label>
          <div className="idea-editor-body">
            <TextBlock
              label="Idea content"
              className="editable-body"
              value={idea.summary}
              placeholder="Start writing your idea…"
              onChange={(summary) => onChange({ summary })}
            />
          </div>
        </div>

        <small className={`editor-save-status ${storageError ? 'save-error' : ''}`} role="status">
          {storageError
            ? 'Could not save in this browser. Keep this tab open to retain your edits.'
            : 'Click any text to edit · Saved in this browser'}
        </small>
      </div>

      {keyConclusion && <div className="conclusion-group">
        <KeyConclusionCard conclusion={keyConclusion} />
      </div>}

      <ProsConsView data={idea.pros_cons} />
      <CompetitorsView data={idea.competitors} />
      <EnrichedJsonView data={idea.rawIdea || idea} ideaId={idea.id} />
    </div>
  )
}
