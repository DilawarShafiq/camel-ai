---
name: ui-test
description: Test or automate any software through its UI from a natural-language goal. Use when the user says "test <app/flow>", "audit the UI of <url>", "click through <feature> and tell me what breaks", or "automate <task> in <app>". Drives web, desktop, or pixels via the uiscout MCP tools — no target-app API needed.
---

# ui-test

Turn a plain-language goal into an executed UI test/automation run.

## When to use
The user wants software driven through its interface: testing a flow, auditing
buttons for dead links, or automating a repetitive task in an app that has no
(accessible) API.

## Steps
1. **Clarify the target and goal.** Which app/URL? What does "done" look like?
   Ask only if genuinely ambiguous.
2. **Pick the driver** (web → desktop → vision, most reliable first).
3. **Delegate execution to the `ui-tester` subagent** with the concrete goal, so
   the multi-step UI driving runs in its own context. For a broad audit across
   several flows, launch one `ui-tester` per flow in parallel.
4. **Human handoff:** tell the user up front that the browser/app will be
   visible and they may be asked to complete 2FA/login themselves; the run pauses
   and resumes automatically.
5. **Synthesize** the subagents' findings into one report: health score, dead
   controls, console errors, broken/confusing flows, and fixes. Offer to write it
   to an HTML file (the `uiscout audit` CLI also produces one for pure web runs).

## Guardrails
- Only automate accounts/software the user is authorized to use.
- Never enter 2FA codes or solve CAPTCHAs on the user's behalf — hand off.
- Report honestly: if a step failed or was skipped, say so.
