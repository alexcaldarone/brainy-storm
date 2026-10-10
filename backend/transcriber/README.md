# Microphone transcriber

Streams the default microphone to Gradium and writes plain text to `data/transcript.txt` in the project root.

## Run

From `backend/transcriber`, copy `.env.example` to `.env` and set your `GRADIUM_API_KEY`. Then run:

```bash
uv run python main.py
```

Run this in an interactive macOS/Linux terminal and allow microphone access if macOS asks. The input must support 24 kHz, mono, 16-bit PCM.

Once the microphone and Gradium connection are ready, the script clears the transcript file. Every five seconds it appends the newly received text as one line and prints it to the terminal. Silent intervals add nothing. The file contains the whole current recording, without timestamps.

- Press **Space** to pause the microphone and save buffered text immediately. Audio waiting to be sent is discarded; results for audio already sent may still be saved while paused.
- Press **Space** again to resume. The existing transcript is preserved, and the next write happens five seconds after resuming.
- Press **Ctrl+C** while recording or paused to save any remaining received text and exit. Words Gradium has not returned yet are not included.

Space works immediately, without Enter, while this terminal is focused. Pausing keeps the Gradium connection open. Normal terminal input and echo are restored on exit, including after an error.

Change `WRITE_INTERVAL_SECONDS = 5` at the top of `main.py` to adjust the interval. Run only one instance against the output file. Other components read the transcript file directly; there is no HTTP server or separate demo client.
