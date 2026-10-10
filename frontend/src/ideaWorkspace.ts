export type GeneratedIdea = { id: string | number; title: string; summary: string }

export type Idea = {
  id: string
  title: string
  summary: string
  tag: string
  votes: number
  pattern: string
  locallyEdited?: boolean
}
export type Session = { name: string; date: string; ideas: number }
export type Workspace = { sessions: Session[]; sessionIdeas: Record<string, Idea[]> }
export const workspaceKey = 'brainy-storm.workspace.v1'

export function readWorkspace(raw: string | null): Workspace | null {
  try {
    const data = JSON.parse(raw || 'null')
    if (!data || !Array.isArray(data.sessions) || !data.sessionIdeas || typeof data.sessionIdeas !== 'object' || Array.isArray(data.sessionIdeas)) return null
    if (!data.sessions.every((s: Session) => s && typeof s.name === 'string' && typeof s.date === 'string' && typeof s.ideas === 'number')) return null
    if (!Object.values(data.sessionIdeas).every(ideas => Array.isArray(ideas) && ideas.every(idea => idea && ['id', 'title', 'summary', 'tag', 'pattern'].every(key => typeof idea[key] === 'string') && typeof idea.votes === 'number'))) return null
    return data as Workspace
  } catch { return null }
}

export function mergeGeneratedIdeas(current: Idea[], incoming: GeneratedIdea[]): Idea[] {
  const merged = incoming.map((idea, index) => {
    const previous = current.find(entry => entry.id === `engine-${idea.id}`)
    return {
      ...idea, id: `engine-${idea.id}`, tag: 'From the conversation', votes: previous?.votes || 0,
      pattern: ['orbit', 'grid', 'signal'][index % 3],
      ...(previous?.locallyEdited ? { title: previous.title, summary: previous.summary, tag: previous.tag, locallyEdited: true } : {}),
    }
  })
  const ids = new Set(merged.map(idea => idea.id))
  return [...merged, ...current.filter(idea => !ids.has(idea.id) && (!idea.id.startsWith('engine-') || idea.locallyEdited))]
}
