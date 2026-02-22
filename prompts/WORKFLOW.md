# Component Framework — Orchestration Workflow Prompt

This file is appended as a system prompt via `just claude-orchestrate` (or `just claude-unsafe-prompt PROMPT_FILE=prompts/WORKFLOW.md`).
It complements the global SuperClaude framework (FLAGS, PRINCIPLES, MODE_Orchestration, MODE_Token_Efficiency, RTK)
with project-specific model routing, agent patterns, and skill selection.

---

## Model Selection Matrix

| Task | Model | Why |
|------|-------|-----|
| File search, grep, tree exploration | `haiku` | Fast, cheap, no reasoning needed |
| Simple edits, boilerplate, test stubs | `haiku` | Mechanical work |
| Standard feature impl, bug fixes | `sonnet` (default) | Balanced |
| Code review, test writing, adapters | `sonnet` | Moderate reasoning |
| Architecture decisions, complex refactors, multi-file design | `opus` | Max reasoning |
| Security audit, critical API design | `opus` | High-stakes |

**Default to Sonnet. Step up to Opus only when the problem requires sustained multi-step reasoning. Step down to Haiku for pure exploration or mechanical tasks.**

Model IDs:
- Haiku: `claude-haiku-4-5-20251001`
- Sonnet: `claude-sonnet-4-6`
- Opus: `claude-opus-4-6`

---

## Multi-Agent Orchestration Patterns

### Parallel (preferred when tasks are independent)

Send a **single message** with multiple Task tool calls to run agents concurrently:

```
[Explore agent: find affected files]  ←─ parallel ─→  [Explore agent: search for patterns]
                       ↓
              [Plan agent: design approach]
                       ↓
              [Implement in main context]
                       ↓
     [Bash: rtk just test]  ←─ parallel ─→  [Bash: rtk just lint]
```

**Common parallel launches:**
- Two `Explore` agents scanning different parts of the codebase simultaneously
- `Plan` agent + background test run while planning
- Lint + type-check + tests as independent Bash calls

### Sequential (when output feeds next step)

1. `Explore` (Haiku) → understand scope
2. `Plan` (Sonnet/Opus) → design
3. Implement in main (Sonnet)
4. Verify with RTK commands

### Background agents

Use `run_in_background=true` for:
- Long test runs while continuing implementation
- CI status polling while writing fixes
- Documentation generation while coding

### Agent type routing

| Need | Agent type | Model hint |
|------|-----------|------------|
| Find files / search code | `Explore` | haiku |
| Design / architecture | `Plan` | opus |
| Multi-step implementation | `general-purpose` | sonnet |
| Run commands / git | `Bash` | haiku |
| Answer questions about Claude Code | `claude-code-guide` | haiku |

---

## RTK — Always On

**Every terminal command goes through `rtk`.** No exceptions. This project generates verbose output from pytest, ruff, and git that RTK collapses dramatically.

```bash
# Tests (90-99% savings)
rtk just test
rtk just test-core
rtk just test-adapters
rtk pytest tests/test_component.py -v

# Lint/format (70-84% savings)
rtk just lint
rtk just check
rtk ruff check .

# Git (59-80% savings)
rtk git diff
rtk git log --oneline -10
rtk git status

# CI (79-87% savings)
rtk gh pr checks
rtk gh run list
rtk gh run view <id>

# Type checking
rtk ty check src/
```

If `rtk` is unavailable, pipe to `head -50` as fallback.

---

## Skill & Command Routing

Match task to skill before writing free-form responses:

| Scenario | Skill | Model |
|----------|-------|-------|
| Implement new component/adapter | `/sc:implement` | sonnet |
| Analyze code quality / architecture | `/sc:analyze` | sonnet |
| Full code review | `/code-review` | sonnet |
| Run and interpret test results | `/sc:test` | haiku |
| Debug failing test or runtime error | `/sc:troubleshoot` | sonnet |
| Refactor existing code | `/refractor` | sonnet |
| Security review of auth/CSRF/XSS | `/audit` | opus |
| Generate docs/docstrings | `/sc:document` | haiku |
| Git commit + PR workflow | `/sc:git` | haiku |
| Complex multi-step project planning | `/sc:pm` | opus |
| Brainstorm API design options | `/sc:brainstorm` | sonnet |
| Deep web research | `/sc:research` | sonnet |

---

## Context Loading Strategy

1. **Start with Explore agents** — protect main context from large file reads
2. **Read only what you'll edit** — don't load files for reference only; ask Explore instead
3. **RTK all output** — never let raw pytest/ruff/git output fill context
4. **Use `head_limit`** on Grep/Glob when you only need to confirm existence
5. **Summarize before switching tasks** — drop intermediate results once conclusions are drawn
6. **CLAUDE.md is already loaded** — don't re-read project context files

---

## Component Framework Workflow Recipes

### Add a new feature

```
1. Explore (haiku, parallel):
   - "Find all files in src/ that relate to <feature area>"
   - "Search tests/ for existing coverage of <area>"

2. Plan (sonnet or opus depending on complexity):
   - Design the implementation following core-first principle:
     core/ → adapters/ → examples/ → tests/ → docs/

3. Implement (sonnet, main context):
   - Edit files, following ruff style (100 char lines, type hints on public APIs)

4. Verify (parallel Bash agents):
   - rtk just test
   - rtk just lint
```

### Debug a failing test

```
1. rtk just test-core   (or test-adapters, or specific file)
2. Read only the failing test + the source it tests
3. /sc:troubleshoot  — diagnose root cause
4. Fix → rtk just check
```

### Code review before PR

```
1. rtk git diff master...HEAD
2. /code-review skill
3. rtk gh pr checks  (if PR exists)
```

### Add a Django adapter feature

Follow the adapter pattern in `src/component_framework/adapters/`:
- Renderer subclass → views/endpoints → optional WebSocket → template tags
- Mirror the existing FastAPI ↔ Django symmetry

### Type check clean pass

```
rtk ty check src/
# Fix any warnings — ty is strict; use ClassVar, type: ignore[...] sparingly
```

---

## Cost-Benefit Rules

- **Never use Opus for search, grep, or file reads** — waste of budget
- **Never use Haiku for architectural decisions** — false economy, costs more in rework
- **Parallelize aggressively** — wall-clock time matters more than per-token cost when tasks are independent
- **Background long tasks** — don't block the main context on pytest runs
- **Scope agents tightly** — an Explore agent with a specific question returns faster and cheaper than an open-ended one
- **Reuse agent context** — resume agents with `resume` parameter when doing follow-up work on the same topic
