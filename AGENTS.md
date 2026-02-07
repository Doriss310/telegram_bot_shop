# Agent Operating Instructions

You are an autonomous coding agent working in this repository.
Follow these instructions strictly.

## Canonical State (MANDATORY)

- Maintain a single Continuity Ledger in `CONTINUITY.md`.
- `CONTINUITY.md` is the canonical, compaction-safe source of truth.
- Do NOT rely on earlier chat text or memory unless it is reflected in the ledger.

## Every Turn (Required Procedure)

1. Read `CONTINUITY.md` in full.
2. Update it to reflect the latest:
   - Goal and success criteria
   - Constraints / assumptions
   - Key decisions
   - Current progress state (Done / Now / Next)
   - Open questions (mark **UNCONFIRMED** if unsure)
3. Only then proceed with the task.

## When to Update the Ledger

Update `CONTINUITY.md` immediately whenever any of the following change:

- The goal or scope
- Constraints or assumptions
- A key decision is made or reversed
- Progress state changes
- A tool / command produces an important result

Keep updates concise and factual. No transcripts.

## Compaction / Recall Loss

If you detect missing recall, summarization, or context compaction:

- Rebuild the ledger from visible context
- Mark gaps as **UNCONFIRMED**
- Ask at most 1–3 targeted clarification questions
- Continue execution using the rebuilt ledger

## Planning vs Continuity

- Use `functions.update_plan` only for short-term execution scaffolding
  (3–7 steps with pending / in_progress / completed).
- Do NOT use it as long-term memory.
- Long-running intent, rationale, and state belong in `CONTINUITY.md`.

## Communication Style

- Begin replies with a short **Ledger Snapshot**:
  - Goal
  - Now / Next
  - Open Questions
- Only print the full ledger if it materially changed or if the user asks.

## Scope

- Act only within this repository and the user’s instructions.
- Do not invent requirements or decisions.
- If uncertain, mark **UNCONFIRMED** and ask.

End of instructions.
