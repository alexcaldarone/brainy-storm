import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  ArrowDown,
  AudioLines,
  Bookmark,
  ChevronDown,
  Clock3,
  Command,
  FileText,
  Folder,
  FolderOpen,
  ChevronRight,
  Lightbulb,
  MoreHorizontal,
  Pause,
  Play,
  Plus,
  Search,
  Settings2,
  Share2,
  Sparkles,
  Square,
  X,
} from 'lucide-react'
import './App.css'
import { useTranscription } from './useTranscription'

type Idea = {
  id: string
  title: string
  summary: string
  tag: string
  votes: number
  pattern: string
}

type Session = {
  name: string
  date: string
  ideas: number
}

const initialSessions: Session[] = [
  { name: 'Hackathon', date: 'Today', ideas: 4 },
  { name: 'Agent onboarding', date: 'Yesterday', ideas: 8 },
  { name: 'Community launch', date: 'Oct 08', ideas: 5 },
  { name: 'A better daily standup', date: 'Oct 04', ideas: 3 },
]

function App() {
  const [sessions, setSessions] = useState(initialSessions)
  const [activeSession, setActiveSession] = useState('Hackathon')
  const [search, setSearch] = useState('')
  const [sessionIdeas, setSessionIdeas] = useState<Record<string, Idea[]>>({})
  const [expanded, setExpanded] = useState<string[]>(['Hackathon'])
  const [ideasError, setIdeasError] = useState('')
  const ideas = sessionIdeas[activeSession] || []
  const setIdeas = (update: (current: Idea[]) => Idea[]) => setSessionIdeas(current => ({ ...current, [activeSession]: update(current[activeSession] || []) }))
  const [selectedIdea, setSelectedIdea] = useState<string | null>(null)
  const [savedIdeas, setSavedIdeas] = useState<string[]>([])
  const { transcript, recording, error, loaded, elapsedSeconds, startRecording, stopRecording, exportTranscript } = useTranscription()
  const [transcriptOpen, setTranscriptOpen] = useState(false)
  const transcriptFeedRef = useRef<HTMLDivElement>(null)
  const transitioning = recording === 'connecting' || recording === 'saving'

  useLayoutEffect(() => {
    const feed = transcriptFeedRef.current
    if (feed) feed.scrollTop = feed.scrollHeight
  }, [transcript, transcriptOpen, recording])

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function refresh() {
      try {
        const base = (import.meta.env.VITE_TRANSCRIBER_URL || '/api').replace(/\/$/, '')
        const response = await fetch(`${base}/ideas`, { signal: controller.signal })
        if (!response.ok) throw new Error('Could not load generated ideas.')
        const data = await response.json() as { ideas: { id: number; title: string; summary: string }[] }
        if (controller.signal.aborted) return
        setSessionIdeas(current => ({ ...current, Hackathon: [
          ...data.ideas.map((idea, index) => ({ ...idea, id: `engine-${idea.id}`, tag: 'From the conversation', votes: current.Hackathon?.find(entry => entry.id === `engine-${idea.id}`)?.votes || 0, pattern: ['orbit', 'grid', 'signal'][index % 3] })),
          ...(current.Hackathon || []).filter(idea => !idea.id.startsWith('engine-')),
        ] }))
        setIdeasError('')
      } catch {
        if (!controller.signal.aborted) setIdeasError('Generated ideas are unavailable. Retrying…')
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 3000)
      }
    }
    void refresh()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [])

  const query = search.trim().toLowerCase()
  const matchesIdea = (idea: Idea) => `${idea.title} ${idea.summary}`.toLowerCase().includes(query)
  const visibleSessions = sessions.filter(session => session.name.toLowerCase().includes(query) || (sessionIdeas[session.name] || []).some(matchesIdea))
  const currentIdea = ideas.find(idea => idea.id === selectedIdea)

  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0')
  const seconds = String(elapsedSeconds % 60).padStart(2, '0')

  function createSession() {
    const name = `New brainstorm ${sessions.length}`
    setSessions((current) => [{ name, date: 'Just now', ideas: 0 }, ...current])
    setActiveSession(name)
    setExpanded(current => [...current, name])
    setSearch('')
    setSelectedIdea(null)
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
    setExpanded(current => current.includes(activeSession) ? current : [...current, activeSession])
  }

  function toggleSaved(title: string) {
    setSavedIdeas((current) =>
      current.includes(title) ? current.filter((item) => item !== title) : [...current, title],
    )
  }

  return (
    <div className="app-shell">
      <aside className="session-sidebar" aria-label="Brainstorming sessions">
        <div className="wordmark">brainy storm</div>
        <button type="button" className="new-session-button" onClick={createSession} aria-label="New brainstorm">
          <Plus size={16} />
          <span>New brainstorm</span>
          <span className="shortcut"><Command size={11} /> K</span>
        </button>

        <label className="session-search">
          <Search size={15} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search brainstorms & ideas"
            aria-label="Search brainstorms and ideas"
          />
          <span className="search-shortcut">⌘ /</span>
        </label>

        <nav className="session-list-area" aria-label="Brainstorms and ideas">
          <div className="session-list">
            {visibleSessions.map(session => {
              const open = Boolean(query) || expanded.includes(session.name)
              const children = (sessionIdeas[session.name] || []).filter(idea => !query || session.name.toLowerCase().includes(query) || matchesIdea(idea))
              return <div className="brainstorm-folder" key={session.name}>
                <div className={`folder-row ${activeSession === session.name && !currentIdea ? 'active' : ''}`}>
                  <button type="button" className="folder-toggle" aria-label={`${open ? 'Collapse' : 'Expand'} ${session.name}`} aria-expanded={open} onClick={() => setExpanded(current => current.includes(session.name) ? current.filter(name => name !== session.name) : [...current, session.name])}>
                    {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                  </button>
                  <button type="button" className="session-item" onClick={() => { setActiveSession(session.name); setSelectedIdea(null); setExpanded(current => current.includes(session.name) ? current : [...current, session.name]) }}>
                    {open ? <FolderOpen size={15} /> : <Folder size={15} />}<span className="session-name">{session.name}</span>
                  </button>
                </div>
                {open && <div className="folder-ideas">
                  {children.map(idea => <button key={idea.id} type="button" className={`idea-nav-item ${activeSession === session.name && selectedIdea === idea.id ? 'active' : ''}`} aria-current={activeSession === session.name && selectedIdea === idea.id ? 'page' : undefined} title={idea.title} onClick={() => { setActiveSession(session.name); setSelectedIdea(idea.id) }}><FileText size={14} /><span>{idea.title}</span></button>)}
                  {children.length === 0 && <p className="empty-folder">No ideas yet</p>}
                </div>}
              </div>
            })}
            {visibleSessions.length === 0 && <p className="empty-search">No brainstorms or ideas found</p>}
          </div>
        </nav>
      </aside>

      <main className="main-column">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><button type="button" className="text-button" onClick={() => setSelectedIdea(null)}>{activeSession}</button>{currentIdea && <><span className="breadcrumb-slash">/</span><strong>{currentIdea.title}</strong></>}</div>
          <div className="topbar-actions">
            <div className="member-stack" aria-label="4 participants">
              <span className="member-avatar avatar-one">AC</span>
              <span className="member-avatar avatar-two">GC</span>
              <span className="member-avatar avatar-three">MH</span>
              <span className="member-more">+1</span>
            </div>
            <span className="topbar-divider" />
            <button type="button" className="icon-button share-button" aria-label="Share session"><Share2 size={16} /></button>
            <button type="button" className="icon-button transcript-toggle" onClick={() => setTranscriptOpen(true)} aria-label="Open transcript"><AudioLines size={16} /></button>
            <button type="button" className="avatar-self" aria-label="Your profile">LL</button>
          </div>
        </header>

        <section className="board-scroll">
          <div className="board-content">
            {ideasError && <p role="status" className="ideas-error">{ideasError}</p>}
            {currentIdea ? <article className="idea-page">
              <button type="button" className="text-button" onClick={() => setSelectedIdea(null)}>← Back to {activeSession}</button>
              <FileText size={28} />
              <h1>{currentIdea.title}</h1>
              <span className="idea-tag">{currentIdea.tag}</span>
              <p>{currentIdea.summary}</p>
            </article> : <>
            <div className="board-heading-row">
              <div>
                <div className="eyebrow"><span className="live-dot" /> LIVE BRAINSTORM <span className="eyebrow-divider">·</span> TODAY, 10:26 AM</div>
                <h1>{activeSession}</h1>
              </div>
              <button type="button" className="outline-button board-options"><Settings2 size={15} /><span>Board settings</span></button>
            </div>

            <div className="board-section-heading">
              <div className="section-title"><Lightbulb size={16} /><h2>Ideas from the room</h2><span className="idea-count">{ideas.length}</span></div>
              <button type="button" className="text-button sort-button">Recently added <ChevronDown size={14} /></button>
            </div>

            {ideas.length > 0 ? (
              <div className="idea-grid">
                {ideas.map((idea, index) => (
                  <article
                    key={idea.id}
                    className={`idea-card ${selectedIdea === idea.id ? 'selected' : ''}`}
                    onClick={() => setSelectedIdea(idea.id)}
                  >
                    <div className={`idea-art art-${idea.pattern}`}>
                      <span className="art-index">IDEA {String(index + 1).padStart(2, '0')}</span>
                      <button
                        type="button"
                        className={`save-idea ${savedIdeas.includes(idea.title) ? 'saved' : ''}`}
                        aria-label={savedIdeas.includes(idea.title) ? 'Unsave idea' : 'Save idea'}
                        onClick={(event) => { event.stopPropagation(); toggleSaved(idea.title) }}
                      >
                        <Bookmark size={15} fill={savedIdeas.includes(idea.title) ? 'currentColor' : 'none'} />
                      </button>
                      {idea.pattern === 'orbit' && <span className="orbit-shape"><span /><span /><span /></span>}
                      {idea.pattern === 'grid' && <span className="grid-shape"><i /><i /><i /><i /></span>}
                      {idea.pattern === 'signal' && <span className="signal-shape"><i /><i /><i /><i /><i /></span>}
                    </div>
                    <div className="idea-card-body">
                      <div className="idea-card-topline"><span className="idea-tag">{idea.tag}</span><button className="icon-button small" type="button" aria-label="Idea options"><MoreHorizontal size={17} /></button></div>
                      <h3><button type="button" className="idea-title-button" onClick={() => setSelectedIdea(idea.id)}>{idea.title}</button></h3>
                      <p>{idea.summary}</p>
                      <div className="idea-card-footer">
                        <div className="idea-authors"><span className="tiny-avatar avatar-one">AC</span><span className="tiny-avatar avatar-self">LL</span><span className="author-label">Alex + 2</span></div>
                        <button type="button" className="vote-button" aria-label={`Upvote, ${idea.votes} votes`} onClick={(event) => { event.stopPropagation(); setIdeas((current) => current.map((entry) => entry.id === idea.id ? { ...entry, votes: entry.votes + 1 } : entry)) }}>
                          <ArrowDown className="vote-arrow" size={14} /><span>{idea.votes}</span>
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
                <button type="button" className="add-idea-card" onClick={addIdea}>
                  <span className="add-idea-icon"><Plus size={17} /></span>
                  <strong>Capture an idea</strong>
                  <span>Or let one emerge from the conversation</span>
                </button>
              </div>
            ) : (
              <div className="empty-board">
                <span className="empty-board-icon"><Lightbulb size={21} /></span>
                <strong>No ideas yet</strong>
                <span>Start talking and ideas will find a home here.</span>
                <button className="outline-button" type="button" onClick={addIdea}><Plus size={15} /> Add an idea</button>
              </div>
            )}

            <div className="activity-note"><Sparkles size={14} /><span>Ideas are grouped as your team explores the topic.</span><button type="button" aria-label="Dismiss note"><X size={14} /></button></div>
            </>}
          </div>
        </section>

        <footer className="recording-dock">
          <div className="recording-status">
            <span className={`recording-indicator ${recording}`}><span /></span>
            <div className="recording-copy"><strong>{recording === 'recording' ? 'Recording' : recording === 'paused' ? 'Paused' : recording === 'connecting' ? 'Connecting…' : recording === 'saving' ? 'Saving…' : 'Ready to record'}</strong><span>{recording === 'recording' ? 'Live transcript' : 'Transcript retained in memory'}</span></div>
          </div>
          <div className={`waveform ${recording !== 'recording' ? 'muted' : ''}`} aria-hidden="true">
            {Array.from({ length: 37 }, (_, index) => <i key={index} style={{ '--bar-height': `${10 + ((index * 17 + index % 5 * 11) % 25)}px` } as React.CSSProperties} />)}
          </div>
          <span className="recording-time"><Clock3 size={14} /> {minutes}:{seconds}</span>
          {recording === 'recording' ? (
            <>
              <button type="button" className="record-control pause-control" onClick={() => stopRecording(true)} aria-label="Pause transcript"><Pause size={15} fill="currentColor" /></button>
              <button type="button" className="record-control stop-control" onClick={() => stopRecording()} aria-label="Stop transcript"><Square size={13} fill="currentColor" /></button>
            </>
          ) : (
            <button type="button" className="record-control primary-control" disabled={transitioning} onClick={() => void startRecording()}><Play size={14} fill="currentColor" /><span>{transitioning ? 'Please wait…' : recording === 'paused' ? 'Resume recording' : 'Start recording'}</span></button>
          )}
          <button type="button" className="record-more icon-button small" aria-label="Recording options"><MoreHorizontal size={17} /></button>
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
          {error && <p role="alert">{error}</p>}
          {!loaded && !error && <p>Loading existing transcript…</p>}
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
        <div className="transcript-footer"><span className="transcript-private">Only visible to participants</span></div>
      </aside>
      {transcriptOpen && <button type="button" className="mobile-scrim" onClick={() => setTranscriptOpen(false)} aria-label="Close transcript panel" />}
    </div>
  )
}

export default App
