# Push destinations

When asked to push to Entire (not GitHub), push to a branch named
`entire/unmirrored/<task-name>`. When asked to publish to GitHub,
push the same commits to a branch without that prefix.

Always follow these instructions when pushing or publishing from this repository.

# Automatic commits and conversation capture

After completing and validating a task, create a commit automatically without
waiting for the user to request a manual commit. Stage only changes belonging to
the task; preserve unrelated user work. For Entire work, use
`entire/unmirrored/<task-name>`. Push when requested, using the destination rules
above.

Keep Entire enabled and use its agent hooks to capture the full available session
conversation, including user prompts, agent responses, tool interactions, and
subagent transcripts where supported. Preserve Entire's secret redaction. Do not
replace the conversation with a summary or a manually reconstructed transcript.

Before committing, check that Entire is tracking the current agent session. After
committing, verify the `Entire-Checkpoint` trailer and its associated transcript.
Entire stores conversations in linked checkpoints, not in the commit message.
When pushing to Entire, ensure the checkpoint data also goes to the `entire`
remote; do not assume the default `origin` checkpoint destination is correct.

If hooks need approval or conversation capture is unavailable, report the blocker
and leave the task changes ready to commit rather than silently creating a commit
without the requested conversation. Never claim that uncaptured history is saved.
