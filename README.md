# Legion

A voice assistant that runs entirely on your own machine. You talk, it answers out loud — no cloud APIs, no accounts, no usage limits, and no internet connection needed once the models are downloaded.

Named after the heavy assault Titan from Titanfall 2, but it behaves more like JARVIS: calm, dry, and occasionally calls you "sir".

```
Microphone: MacBook Air Microphone
Legion is online. Press Enter to talk, Enter again to stop. Ctrl+C to quit.

You: Explain in simple terms why the sky is blue.
Legion: The sky appears blue because of a thing called Rayleigh scattering, sir. It's
when sunlight passes through tiny molecules of gases in the Earth's atmosphere and
scatters in all directions. The shorter, blue wavelengths are scattered more than
longer, red ones, giving the sky its blue colour.
```

## How it works

```mermaid
flowchart LR
    mic([Microphone]) --> stt["faster-whisper<br/>speech → text"]
    stt --> llm["Ollama<br/>local LLM"]
    llm -- "streamed tokens" --> buf["Sentence buffer"]
    buf -- "one sentence at a time" --> tts["Piper<br/>text → speech"]
    tts --> spk([Speakers])
```

| Stage | Library | Runs on |
|---|---|---|
| Speech recognition | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`base.en`, int8) | CPU |
| Language model | [Ollama](https://ollama.com) (`llama3.2:3b` by default) | Local, or another machine on your network |
| Speech synthesis | [Piper](https://github.com/OHF-Voice/piper1-gpl) (`en_GB-alan-medium`) | CPU |

On an 8 GB M1 MacBook Air, a recorded question goes from audio in to spoken answer in about **6 seconds from a cold start**, including loading all three models.

### Design notes

**It starts speaking before the model finishes thinking.** The model's reply streams in token by token. A [`SentenceBuffer`](legion/text.py) releases each sentence the moment it's complete, and a background [`SpeechQueue`](legion/audio.py) thread synthesizes and plays them in order — so the first sentence is already being spoken while later ones are still being generated, and text keeps printing during playback. Very short fragments ("Yes.", "Dr.") are merged forward so the audio doesn't sound choppy.

**You can cut it off.** Audio plays in 0.1-second blocks, so pressing Enter while Legion is talking stops it mid-sentence, drops the rest of the reply, and starts listening. This also fixes a subtle bug in the first version: the reply finishes *printing* long before it finishes *speaking*, so it was natural to press Enter early. The terminal held on to that keypress and handed it to the next prompt, which quietly started a recording and left every later press one step out of phase — "start talking" stopped the recording and "stop" started it. Keys pressed at the wrong moment are now either treated as a cut-in or discarded. The fix is covered by unit tests with a fake speaker, and was verified end to end by driving the real loop through a pseudo-terminal.

**It's genuinely offline.** Models load from the local cache first and only hit the network when something is actually missing. This is verified by running the full pipeline with the Hugging Face endpoint pointed at a dead port.

**Replies are cleaned before they're spoken.** Language models love markdown. [`clean_for_speech`](legion/text.py) strips emphasis, headings, list markers, links, and emoji, so the voice never reads out "asterisk asterisk".

**Silence doesn't produce phantom words.** Whisper tends to invent text when fed pure silence, so voice activity detection trims it before transcription.

**The prompt is short on purpose.** Small models follow brief instructions far better than long ones. An early version told the model to decline questions needing *current* information, and the 3B model overgeneralized that into refusing to name the capital of Australia. The [persona](legion/persona.py) now draws that line explicitly: answer general knowledge, decline only live data like weather or news.

## Setup

Requires macOS, Linux, or Windows with Python 3.11+. The commands below are for macOS with [Homebrew](https://brew.sh).

```bash
brew install ollama uv
brew services start ollama
ollama pull llama3.2:3b

git clone https://github.com/mithransadasivam/legion.git
cd legion
uv sync
```

The first run downloads the speech recognition model (~145 MB) and the voice (~60 MB). After that, everything runs offline.

## Usage

```bash
uv run legion                     # talk: Enter to start recording, Enter to stop, Enter while it's talking to cut in
uv run legion --mic MacBook       # pick a specific microphone
uv run legion --text              # type instead of talking; replies are still spoken
uv run legion --text --quiet      # plain text chat, no audio at all
uv run legion --ask question.wav --save reply.wav   # answer a recording, write the spoken reply to a file
```

On the first voice run, macOS will ask for permission for your terminal to use the microphone.

**Check the microphone line at startup.** If your machine has several audio inputs — a virtual audio driver, a Teams device, an external display — the system default may not be the mic you're speaking into. Legion prints the device it's using; list all of them with `uv run python -m sounddevice`, then choose one by name or number with `--mic`.

### Using a more powerful machine for the model

The model is by far the heaviest stage, and Ollama can serve it over your local network. On a machine with a GPU:

```bash
OLLAMA_HOST=0.0.0.0 ollama serve
ollama pull llama3.1:8b
```

Then point Legion at it:

```bash
uv run legion --host http://192.168.1.50:11434 --model llama3.1:8b
```

Speech recognition and synthesis stay local, so only text crosses the network. Only expose Ollama like this on a network you trust — it has no authentication.

### Configuration

Every option can also be set with an environment variable.

| Flag | Environment variable | Default |
|---|---|---|
| `--model` | `LEGION_MODEL` | `llama3.2:3b` |
| `--host` | `LEGION_OLLAMA_HOST` | `http://127.0.0.1:11434` |
| `--whisper` | `LEGION_WHISPER_MODEL` | `base.en` |
| `--voice` | `LEGION_VOICE` | `en_GB-alan-medium` |
| `--mic` | `LEGION_MIC` | system default input |

Voices are listed at [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices); pass any name in the `en_GB-alan-medium` format.

## Tests

```bash
uv run pytest                              # unit tests
LEGION_INTEGRATION=1 uv run pytest         # also runs the audio round trip
```

The integration test synthesizes a sentence with Piper, transcribes it back with Whisper, and checks the words survive the trip. It's opt-in because it downloads both speech models.

## Project layout

```
legion/
├── app.py       CLI and the main conversation loops
├── brain.py     Streams replies from Ollama and keeps recent conversation history
├── stt.py       Speech recognition (faster-whisper)
├── tts.py       Speech synthesis (Piper)
├── audio.py     Microphone capture and the interruptible background speech queue
├── keys.py      Non-blocking Enter detection, for cutting in mid-reply
├── text.py      Sentence buffering and cleanup for speech
└── persona.py   Legion's personality
tests/
claude-project/  An earlier, no-code version of Legion (see below)
```

## Limitations

- **A 3B model is not Claude or GPT.** It's good at conversation and general knowledge and noticeably weaker at nuanced reasoning. Pointing `--host` at a bigger model on a GPU machine helps a lot.
- **No live information yet.** It can't check the news, weather, or anything else happening right now.
- **Push-to-talk, not a wake word.** You press Enter to talk.
- Conversation history lasts for the session only.

## Roadmap

- [ ] Wake word ("Hey Legion") via openWakeWord, for hands-free use
- [ ] Web search, so it can answer questions about current events
- [ ] Memory that persists between sessions
- [ ] A custom Piper voice

## claude-project/

Before this was code, Legion was a set of instructions for a [claude.ai Project](https://support.claude.com/en/articles/9517075-what-are-projects) — a deep-research persona you use in the Claude app. To set it up, create a Project on claude.ai, open **Set project instructions**, and paste in [`claude-project/legion-project-instructions.md`](claude-project/legion-project-instructions.md). `docs/` holds the original planning notes.
