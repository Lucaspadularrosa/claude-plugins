---
name: dev-toolkit:sdd
description: Spec-Driven Development workflow. Creates, plans, and implements tasks through structured specifications. Subcommands: add <title>, plan [task-file], implement [task-file], go <title>.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
argument-hint: "add <title> | plan [task-file] | implement [task-file] | go <title>"
---

# Spec-Driven Development (SDD)

## Methodology Reference

Before executing any phase, internalize the SDD methodology from:
`@plugins/dev-toolkit/skills/spec-driven-development/SKILL.md`

---

## User Input

```
$ARGUMENTS
```

Parse the first word as the subcommand. The remaining text is the argument.

---

## Subcommand Dispatch

| Input | Action |
|-------|--------|
| `add <title>` | Execute Phase 1: Create Draft Task |
| `plan [task-file]` | Execute Phase 2: Plan and Refine |
| `implement [task-file]` | Execute Phase 3: Implement |
| `go <title>` | Execute Phase 1 + 2 + 3 in sequence |
| *(anything else)* | Show usage help |

---

## Phase 1: Create Draft Task (`add`)

**Goal**: Capture the user's intent and create a structured task file in `draft/`.

### Steps

1. **Scaffold directories**: Run `bash ${CLAUDE_PLUGIN_ROOT}/scripts/create-sdd-dirs.sh` to ensure `.specs/` structure exists.

2. **Read project context**: If any of these exist, read them to understand the project:
   - `CLAUDE.md`
   - `README.md`
   - `docs/` directory (list top-level files)

3. **Generate file name**: Convert the title to kebab-case (e.g., "Implement JWT auth" → `implement-jwt-auth`).

4. **Determine task type**: Based on the title/description, choose one of: `feature`, `bug`, `refactor`, `test`, `docs`, `chore`.

5. **Write task file**: Create `.specs/tasks/draft/<kebab-name>.<type>.md` with this structure:

```markdown
---
title: "<original title>"
type: <type>
status: draft
created: <YYYY-MM-DD>
---

## Initial User Prompt

<title as provided by the user>

## Description

<2-4 sentences expanding on the task using project context. What problem does this solve? What component is affected?>

## Acceptance Criteria

*(To be filled in Phase 2)*

## Architecture Overview

*(To be filled in Phase 2)*

## Implementation Steps

*(To be filled in Phase 2)*
```

6. **Output**: Report the created file path.

---

## Phase 2: Plan and Refine (`plan`)

**Goal**: Transform a draft task into an actionable specification with clear acceptance criteria and implementation steps.

### Steps

1. **Find task file**:
   - If a `task-file` argument was given, use it.
   - Otherwise, auto-detect the newest file in `.specs/tasks/draft/`.

2. **Read task file** completely.

3. **Read project context**: Read `CLAUDE.md`, `README.md`, and any relevant source files mentioned in the task description.

4. **Invoke Best Practices Agent**: Launch the `best-practices` agent to analyze the project stack and get architecture recommendations relevant to this task.

5. **Enrich the task file**: Edit the file in-place to fill in:

   **Acceptance Criteria** — 3-7 verifiable, testable criteria. Each must be checkable without running the full application.

   **Architecture Overview** — Components involved, data flow, key design decisions, trade-offs considered.

   **Implementation Steps** — Ordered steps, each with:
   - `### Step N: <name>`
   - `**Goal**: <what this step achieves>`
   - `**Files**: <files to create or modify>`
   - `**Acceptance**: <how to verify this step is complete>`

   Update frontmatter `status: todo`.

6. **Move file**: Rename/move from `draft/` to `todo/`.

7. **Output**: Report the moved file path and a summary of the plan.

---

## Phase 3: Implement (`implement`)

**Goal**: Execute the implementation steps from the task file, verifying each step before proceeding.

### Steps

1. **Find task file**:
   - If a `task-file` argument was given, use it.
   - Otherwise, auto-detect the newest file in `.specs/tasks/todo/`.

2. **Move to in-progress**: Rename/move file from `todo/` to `in-progress/`. Update frontmatter `status: in-progress`.

3. **Read task file** completely. Identify all Implementation Steps.

4. **For each Implementation Step**:
   a. Read the relevant files listed in `**Files**`.
   b. Implement the changes described in the step.
   c. For steps involving tests: invoke the `testing` agent to generate or update tests.
   d. Verify the step's `**Acceptance**` criterion is met.
   e. Mark the step complete by checking the box if present.

5. **Verify Acceptance Criteria**: After all steps, verify each criterion in the `## Acceptance Criteria` section. Check off completed items.

6. **Move to done**: Rename/move file from `in-progress/` to `done/`. Update frontmatter `status: done`.

7. **Output**: Summary of files changed, acceptance criteria status.

---

## `go` — Full Workflow

Execute Phase 1 → Phase 2 → Phase 3 in sequence using the provided title.

Pause between phases to show status. If any phase fails, stop and report the failure.

---

## Usage Help

If no valid subcommand is provided, output:

```
dev-toolkit:sdd — Spec-Driven Development

Usage:
  /dev-toolkit:sdd add <title>              Create a new task spec
  /dev-toolkit:sdd plan [task-file]         Plan and refine a draft task
  /dev-toolkit:sdd implement [task-file]    Implement a planned task
  /dev-toolkit:sdd go <title>              Full workflow: add → plan → implement

Examples:
  /dev-toolkit:sdd add "Implement JWT authentication"
  /dev-toolkit:sdd plan .specs/tasks/draft/implement-jwt-auth.feature.md
  /dev-toolkit:sdd go "Add rate limiting to API endpoints"
```
