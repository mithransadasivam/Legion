# Legion

A personal deep-research assistant, built as a [claude.ai Project](https://support.claude.com/en/articles/9517075-what-are-projects). Named after the heavy assault Titan from Titanfall 2, but it behaves like JARVIS or FRIDAY — conversational, dry, good company. It knows it's Legion and calls me Sir.

Legion is deliberately **summoned, not ambient.** It lives inside its own Project, so it's there when I go looking for it and nowhere else. Claude outside that Project stays completely normal.

## Setup

1. On claude.ai, create a new Project called **Legion**
2. Open **Set project instructions**
3. Paste in the entire contents of [`legion-project-instructions.md`](legion-project-instructions.md)

That's it. Every chat started inside that Project is Legion; every chat outside it is ordinary Claude.

Projects are available on every surface, including the iOS app, so this works from the phone.

## Why a Project rather than the alternatives

| Where the instructions could live | Reach | Verdict |
|---|---|---|
| Account-level "Instructions for Claude" | Every conversation, everywhere | Too broad — turns *all* of Claude into Legion |
| Inside a Skill | Only when that skill's description matches | Too implicit — Legion appears unpredictably, based on topic |
| **Project instructions** | Every chat inside that Project | **Right.** Enter the Project to summon it; leave to dismiss it |

## Voice

Claude has a real **Voice mode** (beta) on iOS, Android, desktop, and web — a two-way spoken conversation, not just dictation. It speaks answers aloud, web search works inside it, it's on every plan, and there are no voice-specific usage limits.

So Legion talks. Just not in Legion's voice.

You pick from a handful of preset voices (reported as Buttery, Airy, Mellow, Glassy, Rounded). **Custom and cloned voices are impossible by design** — Anthropic restricts the voice list specifically to prevent cloning and impersonation. That's a policy decision rather than a missing feature, so the real Titanfall voice is permanently off the table.

Rough edges: voice mode is turn-based rather than full-duplex and can cut in during a pause (push-to-talk fixes that). Not every result renders on screen mid-call.

*(The documented warning that voice mode "cannot reference the projects and skills you have set up" is scoped to Claude **Cowork** — it doesn't apply to regular Projects.)*

## skills/ — built, not currently deployed

`skills/research-assistant/` holds the same research method packaged as an account-level Skill. It isn't in use: Skills are account-wide and fire whenever their description matches, which would make Legion turn up outside its Project — the opposite of the design above.

It's kept because Skills are the modular path if Legion ever grows several distinct capabilities. For a single capability, Project instructions are simpler and better contained.

## Why not Claude Code skills

The original plan used Claude Code skills reached from the phone via Remote Control. That was dropped: Remote Control only attaches to an already-running local `claude` process and dies when that process exits, which requires an always-on home-base machine. There isn't one — the Mac is a laptop that travels and the gaming PC isn't left running.

claude.ai runs on Anthropic's infrastructure instead, so no machine of mine is in the loop.

Claude Code is still the right tool when the laptop is open and the work touches local repos. It just isn't the foundation.

## docs/

`planning-summary-original.md` — the original planning notes, kept as background. Reflects the earlier Remote Control architecture and predates the rename from Jarvis. Superseded by this README.
