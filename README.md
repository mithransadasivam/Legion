# Legion

A personal AI assistant, built as [Claude Skills](https://claude.com/docs/skills/overview). Named after the heavy assault Titan from Titanfall 2, but it behaves like JARVIS or FRIDAY — conversational, dry, good company. It knows it's Legion, and calls me Sir the way JARVIS does.

The skills here live on my claude.ai account, so the assistant is reachable from the Claude app without any machine of mine being powered on. There is no server to run and no session to keep alive.

## Setup

Legion is assembled from two layers, because they have different reach.

**1. The persona → account-level instructions.** Paste [`persona.md`](persona.md) into Settings → **Instructions for Claude** (click your initials, lower left). These apply to *every* conversation on every device, with no trigger and no prerequisites — which is what makes Legion stay Legion even when no skill fires.

**2. The capabilities → Skills.** Settings → Capabilities → enable **Code execution and file creation**, then **Customize → Skills**, and upload a skill folder such as `skills/research-assistant/`. Skills are account-wide and activate dynamically when relevant.

A skill is a folder containing a `SKILL.md`: YAML frontmatter with a `name` and `description`, then instructions in Markdown. The `description` decides whether Claude invokes the skill at all, so it carries most of the weight.

**Why not put the persona in a Project?** Project instructions only apply inside that Project, so you'd have to remember to enter it. Account-level instructions apply everywhere by default. A Project is still useful for Legion-specific *context* — it just isn't where the character belongs.

## Skills

| Skill | What it does |
|---|---|
| [`research-assistant`](skills/research-assistant/SKILL.md) | Researches a question and reports back with a sourced, verified answer. Publishes anything longer than a screen as an artifact. |

## Voice

Claude has a real **Voice mode** (beta) on iOS, Android, desktop, and web — a two-way spoken conversation, not just dictation. It speaks its answers aloud, web search works inside it, and it's available on every plan with no voice-specific usage limits.

So Legion talks. Just not in Legion's voice.

You pick from a handful of preset voices (reported as Buttery, Airy, Mellow, Glassy, Rounded). **Custom and cloned voices are impossible by design** — Anthropic deliberately restricts the voice list to prevent cloning and impersonation. This isn't a missing feature that might arrive later; it's a policy decision, so the real Titanfall voice is permanently off the table here.

Known rough edges: voice mode is turn-based rather than full-duplex, and it can cut in during a pause (push-to-talk fixes that). Not every result renders on screen mid-call.

**Unverified:** whether account-level Skills actually fire on the mobile apps, and whether they fire inside a voice call. Needs an empirical test before anything gets designed around it. (The documented warning that voice mode "cannot reference the projects and skills you have set up" is scoped to Claude **Cowork**, not to regular Projects or account-level Skills — it doesn't apply here.)

Projects themselves are documented as available on every surface, including mobile.

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
