import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readWorkspace, mergeGeneratedIdeas, foldIdeaUpdates } from './ideaWorkspace.ts'

const idea = { id: 'engine-idea-1', title: 'My title', summary: 'My notes\nSecond paragraph', tag: 'Next steps', votes: 3, locallyEdited: true }

test('polling preserves edits and votes while adding incoming ideas', () => {
  const result = mergeGeneratedIdeas([idea], [{ id: 'idea-1', title: 'Server title', summary: 'Server summary' }, { id: 'idea-2', title: 'New idea', summary: 'New content' }])
  assert.equal(result[0].title, idea.title)
  assert.equal(result[0].summary, idea.summary)
  assert.equal(result[0].tag, idea.tag)
  assert.equal(result[0].votes, 3)
  assert.equal(result[1].title, 'New idea')
})

test('server refresh does not erase edited or manually created pages', () => {
  const manual = { ...idea, id: 'manual-1', locallyEdited: undefined }
  assert.deepEqual(mergeGeneratedIdeas([idea, manual], []), [idea, manual])
})

test('unedited generated ideas receive server updates', () => {
  const result = mergeGeneratedIdeas([{ ...idea, locallyEdited: false }], [{ id: 'idea-1', title: 'Updated', summary: 'Updated summary' }])
  assert.equal(result[0].title, 'Updated')
  assert.equal(result[0].votes, 3)
})

test('single-room storage round-trip retains multiline edits and votes', () => {
  assert.deepEqual(readWorkspace(JSON.stringify([idea])), [idea])
})

test('old workspace retains only the live Hackathon room', () => {
  const workspace = { sessions: [{ name: 'Hackathon', date: 'Today', ideas: 1 }], sessionIdeas: { Hackathon: [idea], 'New brainstorm': [{ ...idea, id: 'manual-1' }] } }
  assert.deepEqual(readWorkspace(JSON.stringify(workspace)), [idea])
  assert.deepEqual(readWorkspace(JSON.stringify({ sessionIdeas: { Hackathon: [] } })), [])
})

test('malformed storage safely falls back to an empty workspace', () => {
  for (const raw of [null, '{', '{}', '[null]', '[{}]', '{"sessionIdeas":{"Hackathon":[{}]}}']) assert.equal(readWorkspace(raw), null)
})

test('new ideas append after manual cards and polling never reorders existing cards', () => {
  const manual = { ...idea, id: 'manual-1' }
  const incoming = [
    { id: 'idea-2', title: 'Newest', summary: '' },
    { id: 'idea-1', title: 'Original', summary: '' },
  ]
  const result = mergeGeneratedIdeas([idea, manual], incoming)
  assert.deepEqual(result.map(i => i.id), ['engine-idea-1', 'manual-1', 'engine-idea-2'])
  assert.deepEqual(mergeGeneratedIdeas(result, incoming).map(i => i.id), result.map(i => i.id))
})

test('idea updates fold by id in first-seen order, merging engine and enrichment fields', () => {
  const topic = [
    { id: 'idea-1', title: 'Scrape catalogs', 'short-summary': 'Scraping.', 'is-currently-discussed': true },
    { id: 'idea-1', competitors: { market_landscape: 'Recommendations', competitors: [{ name: 'Nosto', summary: 'Personalization', differentiator: 'Live discussion' }] } },
    { id: 'idea-2', title: 'Partner', 'short-summary': 'License data.', 'is-currently-discussed': true },
    { id: 'idea-1', title: 'Scrape catalogs', 'short-summary': 'Scraping, but costly.', 'is-currently-discussed': false },
  ].map(message => JSON.stringify(message) + '\n').join('')
  assert.deepEqual(foldIdeaUpdates(topic), [
    { id: 'idea-1', title: 'Scrape catalogs', summary: 'Scraping, but costly.', is_currently_discussed: false, competitors: { market_landscape: 'Recommendations', competitors: [{ name: 'Nosto', summary: 'Personalization', differentiator: 'Live discussion' }] } },
    { id: 'idea-2', title: 'Partner', summary: 'License data.', is_currently_discussed: true },
  ])
})

test('an empty topic or a partially written line yields no ideas', () => {
  assert.deepEqual(foldIdeaUpdates(''), [])
  assert.deepEqual(foldIdeaUpdates('{"id": "idea-1", "tit'), [])
})

test('partial enrichment preserves the engine title, summary and discussion focus', () => {
  const topic = [
    { id: 'idea-1', title: 'Live board', 'short-summary': 'Capture ideas.', 'is-currently-discussed': true },
    { id: 'idea-1', conclusion: 'Try it.', pros_cons: { summary: 'Promising', pros: [], cons: [] } },
  ].map(value => JSON.stringify(value) + '\n').join('')
  const [result] = foldIdeaUpdates(topic)
  assert.equal(result.title, 'Live board')
  assert.equal(result.summary, 'Capture ideas.')
  assert.equal(result.is_currently_discussed, true)
  assert.equal(result.conclusion, 'Try it.')
  assert.deepEqual(result.pros_cons, { summary: 'Promising', pros: [], cons: [] })
})
