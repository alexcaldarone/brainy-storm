import { useLayoutEffect, useRef, useState } from 'react'
import {
  Activity,
  Archive,
  ArrowDown,
  AudioLines,
  Bookmark,
  ChevronDown,
  CircleHelp,
  Clock3,
  Command,
  FileText,
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

const seedIdeas: Idea[] = [
  {
    title: 'A second brain for teams',
    summary:
      'Capture the small sparks that happen between meetings, then bring them back when the team needs them.',
    tag: 'Product direction',
    votes: 8,
    pattern: 'orbit',
  },
  {
    title: 'Make ideas visible',
    summary:
      'A shared canvas that grows with the conversation, not another doc someone has to remember to update.',
    tag: 'Experience',
    votes: 5,
    pattern: 'grid',
  },
  {
    title: 'Agents that listen first',
    summary:
      'Let the room finish a thought. An agent can connect themes, surface questions, and stay out of the way.',
    tag: 'AI workflow',
    votes: 3,
    pattern: 'signal',
  },
]

function App() {
  const [sessions, setSessions] = useState(initialSessions)
  const [activeSession, setActiveSession] = useState('Hackathon')
  const [search, setSearch] = useState('')
  const [ideas, setIdeas] = useState(seedIdeas)
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

  const visibleSessions = sessions.filter((session) =>
    session.name.toLowerCase().includes(search.toLowerCase()),
  )
  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0')
  const seconds = String(elapsedSeconds % 60).padStart(2, '0')

  function createSession() {
    const name = `New brainstorm ${sessions.length}`
    setSessions((current) => [{ name, date: 'Just now', ideas: 0 }, ...current])
    setActiveSession(name)
    setIdeas([])
    setSelectedIdea(null)
  }

  function addIdea() {
    const nextIdea: Idea = {
      title: 'A new idea taking shape',
      summary: 'A fresh thought from the room. Add context as the conversation unfolds.',
      tag: 'Just added',
      votes: 0,
      pattern: 'orbit',
    }
    setIdeas((current) => [...current, nextIdea])
    setSelectedIdea(nextIdea.title)
  }

  function toggleSaved(title: string) {
    setSavedIdeas((current) =>
      current.includes(title) ? current.filter((item) => item !== title) : [...current, title],
    )
  }

  return (
    <div className="app-shell">
      <aside className="session-sidebar" aria-label="Brainstorming sessions">
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
            placeholder="Search sessions"
            aria-label="Search brainstorming sessions"
          />
          <span className="search-shortcut">⌘ /</span>
        </label>

        <div className="session-list-area">
          <div className="nav-section-heading">
            <span>YOUR WORKSPACE</span>
            <button className="icon-button small" type="button" aria-label="Workspace options">
              <MoreHorizontal size={17} />
            </button>
          </div>
          <button className="nav-link" type="button" aria-label="All sessions">
            <Activity size={16} />
            <span>All sessions</span>
          </button>
          <button className="nav-link" type="button" aria-label="Saved ideas">
            <Bookmark size={16} />
            <span>Saved ideas</span>
            {savedIdeas.length > 0 && <span className="nav-count">{savedIdeas.length}</span>}
          </button>

          <div className="session-group-title">
            <span>RECENT</span>
            <ChevronDown size={13} />
          </div>
          <div className="session-list">
            {visibleSessions.map((session) => (
              <button
                key={session.name}
                type="button"
                className={`session-item ${activeSession === session.name ? 'active' : ''}`}
                aria-label={session.name}
                onClick={() => {
                  setActiveSession(session.name)
                  setIdeas(session.name === 'Hackathon' ? seedIdeas : [])
                  setSelectedIdea(null)
                }}
              >
                <span className="session-icon"><FileText size={15} /></span>
                <span className="session-name">{session.name}</span>
                {activeSession === session.name && <span className="active-dot" />}
              </button>
            ))}
            {visibleSessions.length === 0 && <p className="empty-search">No sessions found</p>}
          </div>
        </div>

        <div className="sidebar-bottom">
          <button type="button" className="nav-link" aria-label="Archive"><Archive size={16} /><span>Archive</span></button>
          <button type="button" className="nav-link" aria-label="Help and feedback"><CircleHelp size={16} /><span>Help & feedback</span></button>
          <button type="button" className="profile-row" aria-label="Leonarda Lovrić profile">
            <span className="profile-avatar">LL</span>
            <span className="profile-copy"><strong>Leonarda Lovrić</strong><small>Personal workspace</small></span>
            <MoreHorizontal size={17} />
          </button>
        </div>
      </aside>

      <main className="main-column">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{activeSession}</strong></div>
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
                    key={`${idea.title}-${index}`}
                    className={`idea-card ${selectedIdea === idea.title ? 'selected' : ''}`}
                    onClick={() => setSelectedIdea(idea.title)}
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
                      <h3>{idea.title}</h3>
                      <p>{idea.summary}</p>
                      <div className="idea-card-footer">
                        <div className="idea-authors"><span className="tiny-avatar avatar-one">AC</span><span className="tiny-avatar avatar-self">LL</span><span className="author-label">Alex + 2</span></div>
                        <button type="button" className="vote-button" aria-label={`Upvote, ${idea.votes} votes`} onClick={(event) => { event.stopPropagation(); setIdeas((current) => current.map((entry) => entry.title === idea.title ? { ...entry, votes: entry.votes + 1 } : entry)) }}>
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
