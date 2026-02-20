# AI Engineering Guide: Repository Management

This document defines the standards for how AI assistants (Claude Code or Cursor) should interact with this repository, specifically regarding Issue Tracking and Documentation.

## Issue Management Standards

When asked to "create an issue," "draft a task," or "document a bug," follow this strict protocol:

### 1. Categorization Logic

Select exactly **one** prefix based on the following hierarchy:

- **[BUG]**: Functional errors, crashes, or unintended behavior.
- **[FEAT]**: Brand new functionality or modules.
- **[ENH]**: Improvements to existing features (performance, UI/UX, or logic refinement).
- **[REFACTOR]**: Code cleanup, DRYing logic, or structural changes with no functional impact.
- **[DOCS]**: Changes to README, inline comments, or project documentation.
- **[CHORE]**: Maintenance, dependency updates, or CI/CD workflow changes.

### 2. Issue Structure

All issues must follow this exact Markdown format:

---
**Title:** `[PREFIX] Short, descriptive title`

**Summary:**
> A 1-2 sentence high-level overview of the goal or problem.

**Details:**

- **Context:** (e.g., package name, specific files like `cmd/gopherclaw/main.go`, or environment)
- **Description:** (Steps to reproduce for Bugs; User stories for Feats; Reasoning for Refactors)

**Reproduction (if applicable):**

- [Concrete steps a student can follow to observe the bug firsthand]

**Proposed Implementation:**

- [Briefly describe the technical approach or logic change required]

**Labels:** [bug, enhancement, documentation, refactor, or chore]

---

## AI Workflow Instructions

- **Automation:** If the GitHub CLI (`gh`) is available, you may offer to create the issue directly using `gh issue create`.
- **Linking:** Always check for related existing issues before creating a new one to avoid duplicates.
- **Code Reference:** When drafting an implementation plan, use `@` or backticks to reference specific files currently in the workspace.

## 🎨 Project Tone

Maintain a professional, concise, and engineering-focused tone. Prioritize "Actionable" descriptions over "Vague" descriptions.

## Attribution

All issues must end with a co-authorship line that credits the user and the AI assistant that created the issue. **Use the handle that matches the tool you are running in:**

- **If you are in Cursor:**  
  `*Co-authored by @<github-username> and @cursoragent*`
- **If you are in Claude Code:**  
  `*Co-authored by @<github-username> and @claude*`

Replace `<github-username>` with the repository owner or the user asking for the issue.
