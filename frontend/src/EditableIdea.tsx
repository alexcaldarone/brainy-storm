import { useLayoutEffect, useRef } from 'react'
import type { Idea } from './ideaWorkspace'
import { AbstractSymbol } from './BrandShape'

function TextBlock({ value, label, className, placeholder, onChange, singleLine = false }: {
  value: string; label: string; className: string; placeholder: string; onChange: (value: string) => void; singleLine?: boolean
}) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const input = ref.current
    if (!input) return
    const resize = () => { input.style.height = '0px'; input.style.height = `${input.scrollHeight}px` }
    resize()
    const observer = new ResizeObserver(resize)
    // Watch the container width, not the textarea height we are changing.
    if (input.parentElement) observer.observe(input.parentElement)
    return () => observer.disconnect()
  }, [value])
  return <textarea ref={ref} rows={1} aria-label={label} className={`editable-block ${className}`} value={value} placeholder={placeholder}
    onChange={event => onChange(singleLine ? event.target.value.replace(/[\r\n]+/g, ' ') : event.target.value)}
    onKeyDown={event => { if (singleLine && event.key === 'Enter') { event.preventDefault(); event.currentTarget.blur() } }} />
}

export function EditableIdea({ idea, onChange, storageError }: {
  idea: Idea; onChange: (fields: Partial<Pick<Idea, 'title' | 'summary' | 'tag'>>) => void; storageError: boolean
}) {
  return <>
    <AbstractSymbol className="idea-page-symbol" />
    <div className="idea-editor-title" role="heading" aria-level={1}><TextBlock label="Idea title" className="editable-title" value={idea.title} placeholder="Untitled idea" singleLine onChange={title => onChange({ title })} /></div>
    <input className="editable-tag idea-tag" aria-label="Idea tag" value={idea.tag} placeholder="Add a tag" onChange={event => onChange({ tag: event.target.value })} />
    <div className="idea-editor-body"><TextBlock label="Idea content" className="editable-body" value={idea.summary} placeholder="Start writing your idea…" onChange={summary => onChange({ summary })} /></div>
    <small className={`editor-save-status ${storageError ? 'save-error' : ''}`} role="status">{storageError ? 'Could not save in this browser. Keep this tab open to retain your edits.' : 'Click any text to edit · Saved in this browser'}</small>
  </>
}
