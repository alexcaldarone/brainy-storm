import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readWorkspace, mergeGeneratedIdeas } from './ideaWorkspace.ts'

const idea = { id: 'engine-1', title: 'My title', summary: 'My notes\nSecond paragraph', tag: 'Next steps', votes: 3, pattern: 'orbit', locallyEdited: true }

test('polling preserves edits and votes while adding incoming ideas', () => {
  const result = mergeGeneratedIdeas([idea], [{ id: 1, title: 'Server title', summary: 'Server summary' }, { id: 2, title: 'New idea', summary: 'New content' }])
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
  const result = mergeGeneratedIdeas([{ ...idea, locallyEdited: false }], [{ id: 1, title: 'Updated', summary: 'Updated summary' }])
  assert.equal(result[0].title, 'Updated')
  assert.equal(result[0].votes, 3)
})

test('workspace round-trip retains multiline edits and manual sessions', () => {
  const workspace = { sessions: [{ name: 'New brainstorm', date: 'Just now', ideas: 1 }], sessionIdeas: { 'New brainstorm': [idea] } }
  assert.deepEqual(readWorkspace(JSON.stringify(workspace)), workspace)
})

test('malformed storage safely falls back to an empty workspace', () => {
  for (const raw of [null, '{', '{}', '{"sessions":[null],"sessionIdeas":{}}', '{"sessions":[],"sessionIdeas":{"x":[{}]}}']) assert.equal(readWorkspace(raw), null)
})
