# Legion

A personal AI assistant, built as [Claude Skills](https://claude.com/docs/skills/overview). Named after the heavy assault Titan from Titanfall 2 — terse, tactical, addresses you as Pilot.

The skills here live on my claude.ai account, which means the assistant is available in the Claude app on iPhone, iPad, Mac, and Windows without any machine of mine needing to be powered on. There is no server to run and no session to keep alive.

## Installing a skill

1. Open claude.ai → Settings → Capabilities → Skills
2. Upload the skill's folder — e.g. `skills/research-assistant/`
3. It syncs to every Claude app automatically

A skill is just a folder containing a `SKILL.md`: YAML frontmatter with a `name` and `description`, then instructions in Markdown. The `description` is what decides whether Claude invokes the skill at all, so it carries most of the weight.

## Skills

| Skill | What it does |
|---|---|
| [`research-assistant`](skills/research-assistant/SKILL.md) | Researches a question and reports back with a sourced, verified answer. Publishes anything longer than a screen as an artifact. |

## Design notes

**Voice-first.** Input arrives as iOS keyboard dictation into the Claude app composer — there's no wake word. Two consequences shape every skill here:

- Descriptions match *spoken* phrasing ("what's the deal with…", "catch me up on…"), not typed phrasing.
- Skills avoid clarifying questions. A clarifying question costs two seconds when typing and an entire interaction when speaking one-handed. Better to pick the likeliest reading, state the assumption in one line, and proceed.

**Persona governs tone, never substance.** The Legion voice is explicitly subordinate to being correct — if staying in character would cost a real caveat, the character gets dropped. A terse assistant that's wrong is worse than a wordy one that's right.

**Persona lives in the skill for now.** Once there are several skills, it should move to a Project so it isn't duplicated across every `SKILL.md`.

## Audio voice

Legion's *written* voice is here. His *actual* voice is not, and can't be with this architecture — claude.ai Skills produce text, and the Claude app offers no hook for custom text-to-speech. Getting the real thing would mean a self-hosted voice pipeline (Home Assistant + a custom-trained Piper voice, or similar), which is a different and much larger project. See `docs/` for the architecture that was evaluated and set aside.

## Why not Claude Code skills

The original plan used Claude Code skills reached from the phone via Remote Control. That was dropped: Remote Control only attaches to an already-running local `claude` process and dies when that process exits, which requires an always-on home-base machine. There isn't one — the Mac is a laptop that travels and the gaming PC isn't left running.

Account-level Skills run on Anthropic's infrastructure instead, so no machine of mine is in the loop. For a research assistant there was no capability worth the extra infrastructure.

Claude Code is still the right tool when the laptop is open and the work touches local repos. It just isn't the foundation.

## docs/

`planning-summary-original.md` — the original planning notes, kept as background. It reflects the earlier Remote Control architecture described above, and predates the rename from Jarvis. Superseded by this README.
