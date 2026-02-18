# CLAUDE.md

## Project Standards

- **Language:** Use the primary language and version detected in the workspace
- **Workflow:** Use `.github/prompts/ISSUE_PROMPT.md` for all issue creation and task documentation tasks

## Git Commit Standards

- **Format:** `<type>(<scope>): <description>` (Conventional Commits).
- **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
- **Logic:** 
    1. Run `git log -n 5` to confirm existing scope naming conventions.
    2. Use the imperative mood (e.g., "add connection wizard").
    3. **Issue Linking**: If the change resolves an open issue, append `(fixes #ID)` or `(closes #ID)` to the end of the description.
    4. **Verification**: Check `.github/prompts/ISSUE_PROMPT.md` to ensure the commit fulfills the "Acceptance Criteria" defined in the task.
- **Example**: `feat(ui): connection wizard with test flow (fixes #12)`

## Issue Tracking

When asked to draft or create a GitHub issue:

1. **Context Check**: Identify the primary programming language and framework of the current project (e.g., Go for GopherClaw, React/TS for folio).
2. **Read**: Load instructions from `.github/prompts/ISSUE_PROMPT.md`.
3. **Implementation**: In the "Proposed Implementation" section, provide code snippets or logic suggestions using the **current project's language and best practices.**
4. **Follow**: Use the prefix logic and structure defined in `.github/prompts/ISSUE_PROMPT.md`