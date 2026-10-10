We work on a real-time brainstorming companion that provides a webapp that listens to a team brainstorming, transcribes, processes and live updates a frontend with new ideas as they pop up.

The overall system diagram:

```
[AUDIO] ---> [TRANSCRIPTION (Gradio/Gradium STT)] ---> (appends) ---> [data/transcript.txt]
                                                                              │
                                                                              ▼ (reads every few s)
[GEMINI API] <====== (API call / Structured Output) ===================> [ENGINE]
                                                                              │
                                                                              ▼ (reads & writes)
[FRONTEND (React)] <── (reads/displays) ─── [data/ideas.json] ◄─── (reads/updates) ─── [ENRICHMENT]
```

Our focus is the engine part. We assume the transcribe.txt to be present, and we read and update ideas.json accordingly. The egine is a simple, minimal `while True` python loop that pools the `data/transcript.txt` and processes the text in chunks, then writes to `data/ideas.json`. No overegineering, just minimal working prototype.