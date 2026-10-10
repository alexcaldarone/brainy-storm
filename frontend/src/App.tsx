import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  ArrowDown,
  Columns3,
  LayoutGrid,
  AudioLines,
  Clock3,
  FileText,
  Info,
  MoreHorizontal,
  Play,
  Pause,
  RotateCcw,
  Download,
  Plus,
  X,
} from 'lucide-react'
import './App.css'
import { AbstractSymbol, BrandShape, RecordingShape } from './BrandShape'
import { EditableIdea } from './EditableIdea'
import { AvatarGroup } from './AvatarGroup'
import { mergeGeneratedIdeas, readWorkspace, workspaceKey } from './ideaWorkspace'
import type { GeneratedIdea, Idea } from './ideaWorkspace'
import { useTranscription } from './useTranscription'

const sessionParticipants = [
  { initials: 'AC', color: 'avatar-one' },
  { initials: 'GC', color: 'avatar-two' },
  { initials: 'MH', color: 'avatar-three' },
  { initials: 'LL', color: 'avatar-self' },
]

function InfoBanner({ message, role = 'status' }: { message: string; role?: 'status' | 'alert' }) {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null
  return <div className="info-banner" role={role}><Info size={16} aria-hidden="true" /><span>{message}</span><button type="button" aria-label="Dismiss notification" onClick={() => setDismissed(true)}><X size={16} /></button></div>
}

function thumbnailUrl(thumbnail?: string | null) {
  if (!thumbnail || /^(?:https?:|data:|blob:)/.test(thumbnail)) return thumbnail || ''
  const base = (import.meta.env.VITE_ENRICHMENT_URL || '/api/enrichment').replace(/\/$/, '')
  return thumbnail.startsWith('/ideas/') ? `${base}${thumbnail}` : thumbnail
}

function App() {
  const [restored] = useState(() => {
    try { return readWorkspace(localStorage.getItem(workspaceKey)) } catch { return null }
  })
  const [storageError, setStorageError] = useState(false)
  const activeSession = 'Brainstorm'
  const [ideas, setIdeas] = useState<Idea[]>(restored?.sessionIdeas.Hackathon || [])
  const [restarting, setRestarting] = useState(false)
  const [restartError, setRestartError] = useState('')
  const restartDialog = useRef<HTMLDialogElement>(null)
  const pollingGeneration = useRef(0)
  const resetInProgress = useRef(false)
  const [ideasError, setIdeasError] = useState('')
  const [layout, setLayout] = useState<'horizontal' | 'grid'>('horizontal')
  const [focusedIdeaId, setFocusedIdeaId] = useState<string | null>(null)
  const [selectedIdea, setSelectedIdea] = useState<string | null>(null)
  const { transcript, recording, error, loaded, elapsedSeconds, startRecording, stopRecording, resetMemory, exportTranscript } = useTranscription()
  const [transcriptOpen, setTranscriptOpen] = useState(false)
  const transcriptFeedRef = useRef<HTMLDivElement>(null)
  const discussedCardRef = useRef<HTMLElement | null>(null)
  const transitioning = recording === 'connecting' || recording === 'saving' || restarting

  useEffect(() => {
    try {
      localStorage.setItem(workspaceKey, JSON.stringify({ sessions: [{ name: 'Brainstorm', date: 'Today', ideas: ideas.length }], sessionIdeas: { Hackathon: ideas } }))
      // Report the result of synchronizing with browser storage.
      // oxlint-disable-next-line react/set-state-in-effect
      setStorageError(false)
    } catch { setStorageError(true) }
  }, [ideas])

  useLayoutEffect(() => {
    const feed = transcriptFeedRef.current
    if (feed) feed.scrollTop = feed.scrollHeight
  }, [transcript, transcriptOpen, recording])

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function refresh() {
      if (resetInProgress.current) { timer = setTimeout(refresh, 3000); return }
      const generation = pollingGeneration.current
      try {
        const base = (import.meta.env.VITE_ENRICHMENT_URL || '/api/enrichment').replace(/\/$/, '')
        const response = await fetch(`${base}/ideas`, { signal: controller.signal })
        if (!response.ok) throw new Error('Could not load generated ideas.')
        const payload = await response.json() as GeneratedIdea[] | { ideas: GeneratedIdea[] }
        const data = Array.isArray(payload) ? payload : payload.ideas
        if (controller.signal.aborted || generation !== pollingGeneration.current) return
        setIdeas(current => mergeGeneratedIdeas(current, data))
        const focused = data.find(idea => idea.is_currently_discussed)
        setFocusedIdeaId(focused ? `engine-${focused.id}` : null)
        setIdeasError('')
      } catch {
        if (!controller.signal.aborted) {
          setFocusedIdeaId(null)
          setIdeasError('Showing saved ideas. Live updates are unavailable; retrying…')
        }
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 3000)
      }
    }
    void refresh()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [])

  const currentIdea = ideas.find(idea => idea.id === selectedIdea)

  const visibleFocusedIdeaId = !currentIdea
    ? ideas.find(idea => idea.id === focusedIdeaId)?.id
    : undefined

  useLayoutEffect(() => {
    if (!visibleFocusedIdeaId) return
    discussedCardRef.current?.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
      block: 'nearest',
      inline: 'nearest',
    })
  }, [visibleFocusedIdeaId, layout])

  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0')
  const seconds = String(elapsedSeconds % 60).padStart(2, '0')

  function downloadMemory() {
    const url = URL.createObjectURL(new Blob([JSON.stringify({ exportedAt: new Date().toISOString(), ideas, transcript }, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'brainstorm-memory.json'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  async function restartBrainstorm() {
    resetInProgress.current = true
    setRestarting(true)
    setRestartError('')
    pollingGeneration.current += 1
    try {
      await resetMemory()
      setIdeas([])
      setSelectedIdea(null)
      setFocusedIdeaId(null)
      restartDialog.current?.close()
      await startRecording()
    } catch (error) {
      setRestartError(error instanceof Error ? error.message : 'Could not restart. Please try again.')
    } finally {
      pollingGeneration.current += 1
      resetInProgress.current = false
      setRestarting(false)
    }
  }

  function addIdea() {
    const nextIdea: Idea = {
      id: crypto.randomUUID(),
      title: 'A new idea taking shape',
      summary: 'A fresh thought from the room. Add context as the conversation unfolds.',
      tag: 'Just added',
      votes: 0,
      pattern: 'orbit',
    }
    setIdeas((current) => [...current, nextIdea])
    setSelectedIdea(nextIdea.id)
  }

  const collaboratorActions = (
    <div className="collaborator-actions">
      <AvatarGroup participants={sessionParticipants} />
      {!currentIdea && <div className="layout-picker" role="group" aria-label="Card layout">
        <button type="button" aria-label="Horizontal layout" title="Horizontal layout" aria-pressed={layout === 'horizontal'} onClick={() => setLayout('horizontal')}><Columns3 size={16} /></button>
        <button type="button" aria-label="Grid layout" title="Grid layout" aria-pressed={layout === 'grid'} onClick={() => setLayout('grid')}><LayoutGrid size={16} /></button>
      </div>}
      <button type="button" className="icon-button transcript-toggle" onClick={() => setTranscriptOpen(true)} aria-label="Open transcript"><AudioLines size={16} /></button>
    </div>
  )

  return (
    <div className="app-shell">
      <dialog ref={restartDialog} className="restart-dialog" aria-labelledby="restart-title" onCancel={event => { if (restarting) event.preventDefault() }}>
        <button type="button" className="icon-button restart-dialog-close" aria-label="Cancel restart" disabled={restarting} onClick={() => restartDialog.current?.close()}><X size={18} /></button>
        <h2 id="restart-title">Restart brainstorm?</h2>
        <p>Are you sure you want to clear the memory and start over?</p>
        <p>This clears all ideas and the transcript. Download your memory first if you want to keep a copy.</p>
        {restartError && <p role="alert">{restartError}</p>}
        <div className="restart-actions">
          <button className="record-control primary-control" disabled={restarting} onClick={() => void restartBrainstorm()}>{restarting ? 'Restarting…' : 'Clear memory and restart'}</button>
          <button className="outline-button" disabled={restarting} onClick={downloadMemory}><Download size={14} /> Download memory</button>
        </div>
      </dialog>
      <main className="main-column">
        <section className={`board-scroll ${!currentIdea && layout === 'horizontal' ? 'horizontal-board' : ''}`}>
          <div className="board-content">
            {ideasError && <InfoBanner key={ideasError} message={ideasError} />}
            {currentIdea ? <article className="idea-page">
              <div className="idea-page-banner"><BrandShape variant={ideas.findIndex(idea => idea.id === currentIdea.id) % 6} /></div>
              <div className="idea-page-toolbar"><button type="button" className="idea-back-button" onClick={() => setSelectedIdea(null)}>← Back to {activeSession}</button>{collaboratorActions}</div>
              <EditableIdea key={currentIdea.id} idea={currentIdea} storageError={storageError} onChange={fields => setIdeas(current => current.map(idea => idea.id === currentIdea.id ? { ...idea, ...fields, locallyEdited: true } : idea))} />
            </article> : <>
            <div className="board-heading-row">
              <div>
                <h1>{activeSession}</h1>
              </div>
              {collaboratorActions}
            </div>

            {ideas.length > 0 ? (
              <div className={`idea-grid ${layout === 'horizontal' ? 'idea-rail' : ''}`} tabIndex={0} role="region" aria-label="Ideas">
                {ideas.map((idea, index) => (
                  <article
                    key={idea.id}
                    ref={visibleFocusedIdeaId === idea.id ? discussedCardRef : undefined}
                    className={`idea-card ${focusedIdeaId === idea.id ? 'discussion-focus' : ''}`}
                    onClick={() => setSelectedIdea(idea.id)}
                  >
                    <div className={`idea-art art-${idea.pattern}`}>
                      <BrandShape variant={index % 6} />
                      {idea.thumbnail && <img className="idea-thumbnail" src={thumbnailUrl(idea.thumbnail)} alt="" onError={event => { event.currentTarget.style.display = 'none' }} />}
                    </div>
                    <div className="idea-card-body">
                      <div className="idea-card-topline">{focusedIdeaId === idea.id && <span className="discussion-label">Discussing now</span>}<span className="idea-tag">{idea.tag}</span><button className="icon-button small" type="button" aria-label="Idea options"><MoreHorizontal size={17} /></button></div>
                      <h3><button type="button" className="idea-title-button" onClick={() => setSelectedIdea(idea.id)}>{idea.title || 'Untitled idea'}</button></h3>
                      <p>{idea.summary}</p>
                      <div className="idea-card-footer">
                        <AvatarGroup participants={sessionParticipants} />
                        <button type="button" className="vote-button" aria-label={`Upvote, ${idea.votes} votes`} onClick={(event) => { event.stopPropagation(); setIdeas((current) => current.map((entry) => entry.id === idea.id ? { ...entry, votes: entry.votes + 1 } : entry)) }}>
                          <ArrowDown className="vote-arrow" size={14} /><span>{idea.votes}</span>
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
                <button type="button" className="add-idea-card" onClick={addIdea}>
                  <span className="add-idea-icon"><AbstractSymbol /></span>
                  <strong>Capture an idea</strong>
                  <span>Or let one emerge from the conversation</span>
                </button>
              </div>
            ) : (
              <div className="empty-board">
                <span className="empty-board-icon"><AbstractSymbol /></span>
                <strong>No ideas yet</strong>
                <span>Start talking and ideas will find a home here.</span>
                <button className="outline-button" type="button" onClick={addIdea}><Plus size={15} /> Add an idea</button>
              </div>
            )}

            </>}
          </div>
        </section>

        <footer className="recording-dock">
          <RecordingShape active={recording === 'recording'} />
          <span className="recording-time"><Clock3 size={14} /> {minutes}:{seconds}</span>
          <button
            type="button"
            className="record-control primary-control"
            disabled={transitioning}
            aria-busy={transitioning}
            onClick={() => recording === 'recording' ? stopRecording(true) : void startRecording()}
          >
            {recording === 'recording' || recording === 'saving' ? <Pause size={13} /> : <Play size={14} fill="currentColor" />}
            <span>{recording === 'connecting' ? 'Starting…' : recording === 'saving' ? 'Pausing…' : recording === 'recording' ? 'Pause' : recording === 'paused' ? 'Resume' : 'Start'}</span>
          </button>
          <button type="button" className="record-control restart-control" disabled={transitioning} onClick={() => { setRestartError(''); restartDialog.current?.showModal() }}><RotateCcw size={14} /><span>Restart</span></button>
        </footer>
      </main>

      <aside className={`transcript-sidebar ${transcriptOpen ? 'mobile-open' : ''}`} aria-label="Live transcript">
        <div className="transcript-header">
          <div><div className="transcript-title-row"><h2>Transcript</h2><button type="button" className="icon-button small mobile-close" onClick={() => setTranscriptOpen(false)} aria-label="Close transcript"><X size={16} /></button></div></div>
          <details className="transcript-options" onBlur={event => {
            if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false
          }} onKeyDown={event => {
            if (event.key === 'Escape') {
              event.currentTarget.open = false
              event.currentTarget.querySelector('summary')?.focus()
            }
          }}>
            <summary className="icon-button small" aria-label="Transcript options"><MoreHorizontal size={18} /></summary>
            <div className="transcript-options-menu">
              <button type="button" className="transcript-export" onClick={event => {
                exportTranscript()
                const menu = event.currentTarget.closest('details')
                if (menu) {
                  menu.open = false
                  menu.querySelector('summary')?.focus()
                }
              }}><FileText size={14} /><span>Export transcript</span></button>
            </div>
          </details>
        </div>
        <div className="transcript-feed" ref={transcriptFeedRef} aria-live="polite">
          {error && <InfoBanner key={error} message={error} role="alert" />}
          {!loaded && !error && <InfoBanner message="Loading existing transcript…" />}
          {loaded && transcript.length === 0 && <p>Start recording to capture your conversation.</p>}
          <div className="transcript-date"><span />TODAY<span /></div>
          {transcript.map((line, index) => (
            <article className={`transcript-line ${index === transcript.length - 1 && recording === 'recording' ? 'currently-speaking' : ''}`} key={index}>
              <span className={`speaker-avatar ${line.initials === 'LL' ? 'avatar-self' : line.initials === 'AC' ? 'avatar-one' : line.initials === 'GC' ? 'avatar-two' : 'avatar-three'}`}>{line.initials}</span>
              <div className="transcript-line-content"><div className="speaker-meta"><strong>{line.person}</strong><time>{line.time}</time></div><p>{line.text}</p></div>
            </article>
          ))}
          {recording === 'recording' && <div className="transcript-capture"><span className="capture-avatar">···</span><span>Listening for the next thought</span><span className="capture-pulse" /></div>}
        </div>
      </aside>
      {transcriptOpen && <button type="button" className="mobile-scrim" onClick={() => setTranscriptOpen(false)} aria-label="Close transcript panel" />}
    </div>
  )
}

export default App
