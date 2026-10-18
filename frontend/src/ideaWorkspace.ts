export type CompetitorItem = {
  name: string
  summary: string
  differentiator: string
}

export type CompetitorEnrichment = {
  competitors: CompetitorItem[]
  market_landscape: string
}

export type ProConItem = {
  point: string
  category: string
  severity_or_impact: 'High' | 'Medium' | 'Low'
}

export type ProsConsEnrichment = {
  summary: string
  pros: ProConItem[]
  cons: ProConItem[]
}

export type GeneratedIdea = {
  id: string
  title: string
  summary: string
  is_currently_discussed?: boolean
  competitors?: CompetitorEnrichment
  pros_cons?: ProsConsEnrichment
  conclusion?: string
}

export type Idea = GeneratedIdea & {
  tag: string
  votes: number
  locallyEdited?: boolean
  rawIdea?: GeneratedIdea
}

// A partial idea from the engine or enricher, keyed by id.
type IdeaUpdateMessage = Partial<Omit<GeneratedIdea, 'summary' | 'is_currently_discussed'>> & {
  id: string
  'short-summary'?: string
  'is-currently-discussed'?: boolean
}

export function foldIdeaUpdates(topic: string): GeneratedIdea[] {
  const ideas = new Map<string, GeneratedIdea>()
  // A publisher may be mid-write: only complete lines are messages.
  for (const line of topic.slice(0, topic.lastIndexOf('\n') + 1).split('\n')) {
    if (!line.trim()) continue
    const { id, 'short-summary': summary, 'is-currently-discussed': discussed, ...fields } = JSON.parse(line) as IdeaUpdateMessage
    ideas.set(id, {
      ...(ideas.get(id) || { id, title: '', summary: '' }),
      ...fields,
      ...(summary !== undefined && { summary }),
      ...(discussed !== undefined && { is_currently_discussed: discussed }),
    })
  }
  return [...ideas.values()]
}

export const workspaceKey = 'brainy-storm.workspace.v1'

export function readWorkspace(raw: string | null): Idea[] | null {
  try {
    const data = JSON.parse(raw || 'null')
    // On the first load after cleanup, keep only the old workspace's live room.
    const ideas = Array.isArray(data) ? data : data?.sessionIdeas?.Hackathon
    if (!Array.isArray(ideas) || !ideas.every(idea => idea && ['id', 'title', 'summary', 'tag'].every(key => typeof idea[key] === 'string') && typeof idea.votes === 'number')) return null
    return ideas
  } catch { return null }
}

export function mergeGeneratedIdeas(current: Idea[], incoming: GeneratedIdea[]): Idea[] {
  const merged: Idea[] = incoming.map(idea => {
    const previous = current.find(entry => entry.id === `engine-${idea.id}`)
    return {
      ...idea,
      rawIdea: idea,
      id: `engine-${idea.id}`,
      tag: previous?.tag || 'From the conversation',
      votes: previous?.votes || 0,
      ...(previous?.locallyEdited ? { title: previous.title, summary: previous.summary, tag: previous.tag, locallyEdited: true } : {}),
    }
  })
  const updates = new Map(merged.map(idea => [idea.id, idea]))
  const existingIds = new Set(current.map(idea => idea.id))
  return [
    ...current.filter(idea => updates.has(idea.id) || !idea.id.startsWith('engine-') || idea.locallyEdited).map(idea => updates.get(idea.id) || idea),
    ...merged.filter(idea => !existingIds.has(idea.id)),
  ]
}
