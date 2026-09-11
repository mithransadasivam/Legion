# Legion

A personal AI assistant, built as [Claude Skills](https://claude.com/docs/skills/overview). Named after the heavy assault Titan from Titanfall 2, but it behaves like JARVIS or FRIDAY — conversational, dry, good company. It knows it's Legion, and calls me Sir the way JARVIS does.

The skills here live on my claude.ai account, so the assistant is reachable from the Claude app without any machine of mine being powered on. There is no server to run and no session to keep alive.

## Installing a skill

1. Open claude.ai → Settings → Capabilities → enable **Code execution and file creation**
2. Under that, open **Customize → Skills**
3. Upload the skill's folder — e.g. `skills/research-assistant/`

A skill is a folder containing a `SKILL.md`: YAML frontmatter with a `name` and `description`, then instructions in Markdown. The `description` is what decides whether Claude invokes the skill at all, so it carries most of the weight.

## Skills

| Skill | What it does |
|---|---|
| [`research-assistant`](skills/research-assistant/SKILL.md) | Researches a question and reports back with a sourced, verified answer. Publishes anything longer than a screen as an artifact. |

## Voice

Claude has a real **Voice mode** (beta) on iOS, Android, desktop, and web — a two-way spoken conversation, not just dictation. It speaks its answers aloud, web search works inside it, and it's available on every plan with no voice-specific usage limits.

So Legion talks. Just not in Legion's voice.

You pick from a handful of preset voices (reported as Buttery, Airy, Mellow, Glassy, Rounded). **Custom and cloned voices are impossible by design** — Anthropic deliberately restricts the voice list to prevent cloning and impersonation. This isn't a missing feature that might arrive later; it's a policy decision, so the real Titanfall voice is permanently off the table here.

Known rough edges: voice mode is turn-based rather than full-duplex, and it can cut in during a pause (push-to-talk fixes that). Not every result renders on screen mid-call.

**Unverified:** whether account-level Skills actually fire on the mobile apps, and whether they fire inside a voice call. Anthropic's Skills documentation lists web chat, Cowork, Claude Code, and Microsoft 365 as supported surfaces — the phone apps aren't named. Needs an empirical test before anything gets designed around it.

## Design notes

**Voice-first.** Requests arrive spoken, so skills are written for speech:

- Descriptions match *spoken* phrasing ("what's the deal with…", "catch me up on…"), not typed phrasing.
- Skills avoid clarifying questions. A clarifying question costs two seconds when typing and an entire interaction when speaking one-handed. Better to pick the likeliest reading, state the assumption in one line, and carry on.

**Character never costs accuracy.** The persona is explicitly subordinate to being correct — a joke that buries a real caveat isn't worth making.

**Persona lives in the skill for now.** Once there are several skills it should move to a Project, so it isn't duplicated across every `SKILL.md`.

## Why not Claude Code skills

The original plan used Claude Code skills reached from the phone via Remote Control. That was dropped: Remote Control only attaches to an already-running local `claude` process and dies when that process exits, which requires an always-on home-base machine. There isn't one — the Mac is a laptop that travels and the gaming PC isn't left running.

Account-level Skills run on Anthropic's infrastructure instead, so no machine of mine is in the loop.

Claude Code is still the right tool when the laptop is open and the work touches local repos. It just isn't the foundation.

## docs/

`planning-summary-original.md` — the original planning notes, kept as background. Reflects the earlier Remote Control architecture and predates the rename from Jarvis. Superseded by this README.
