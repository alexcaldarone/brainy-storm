# Assumptions and Open Questions

## Assumptions
- Repositories have comprehensive, reliable test suites capable of proving the correctness of automated patches.
- Diff-based AST filtering can reliably isolate relevant context without omitting critical dependencies needed by the model.
- Snapshot caching for ephemeral Docker containers will adequately mitigate the 5-minute cold-start delay in CI runners.
- Mandating GPG signing and removing auto-merge functionality satisfies all SOC2 compliance liability standards.

## Open questions
- Which LLM vendor or self-hosted deployment model will be utilized to guarantee proprietary code privacy?
- What specific baseline safety scoring framework will be presented in the interactive PR diff to establish developer trust?
- How will the sandboxed environment securely handle repositories requiring external services, private registries, or complex environment variables?
- What is the actual measured financial impact of container snapshot caching versus the anticipated 300% CI cost spike?
