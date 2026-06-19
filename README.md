# Media2Txt Pro Community

A desktop community edition for transcribing YouTube/local media and generating structured summaries with local Whisper + Ollama.

## Community features
- Single YouTube URL or multiple URLs
- Local video/audio batch input
- Transcript export to `.txt`
- Summary output in Traditional Chinese or English
- Basic domain-aware summarizer
- Local Whisper model support
- CPU / GPU auto detection with fallback
- Pause / Resume / Stop
- GUI debug panel and ETA

## Requirements
- Python 3.10+
- Ollama running locally
- Local faster-whisper model placed at `models/faster-whisper-large-v3`

## Quick start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Put the model in:
   ```
   models/faster-whisper-large-v3
   ```
3. Start Ollama and ensure your model is available.
4. Run:
   ```bash
   run.bat
   ```

## Notes
- Community edition intentionally keeps only the basic summarization workflow.
- Advanced expert templates, report export, history, automation, and commercial support belong in the Pro edition.

## Windows CUDA native-crash isolation

Transcription now runs in an isolated child process by default. A native CTranslate2/CUDA access violation such as `0xC0000005` no longer needs to terminate the Qt GUI. The parent process detects the child exit code and retries transcription in a CPU child process.

Default stability settings:

- GPU compute type: `int8_float16`
- CPU compute type: `int8`
- Long-video threshold: 15 minutes
- Very-long-video threshold: 40 minutes
- Subprocess isolation: enabled
