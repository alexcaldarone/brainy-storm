# Assumptions and Open Questions

## Assumptions
- Existing unit test suites provide sufficient coverage to validate generated patches without introducing regressions
- Developers will actively review suggested patches rather than rubber-stamping AI-generated commits
- AST diff chunking captures sufficient context for LLMs to generate correct and functional multi-file fixes
- Container snapshot caching will adequately eliminate ephemeral Docker cold-start delays in CI

## Open questions
- Which LLM provider meets enterprise data privacy requirements to prevent proprietary IP leakage and model training on internal code?
- How much additional infrastructure cost does snapshot caching introduce relative to the savings gained?
- What specific metrics will constitute the 'safety score' presented in the PR comments to guide reviewer approvals?
- How will the bot handle integration test suites that require external network calls or persistent state unavailable in an isolated sandbox?
