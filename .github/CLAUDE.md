# CLAUDE.md

## Project Standards

- **Language:** Use the primary language and version detected in the workspace
- **Workflow:** Use `.github/prompts/ISSUE_PROMPT.md` for all issue creation and task documentation tasks

## Issue Tracking

When asked to draft or create a GitHub issue:

1. **Context Check**: Identify the primary programming language and framework of the current project (e.g., Go for GopherClaw, React/TS for folio).
2. **Read**: Load instructions from `.github/prompts/ISSUE_PROMPT.md`.
3. **Implementation**: In the "Proposed Implementation" section, provide code snippets or logic suggestions using the **current project's language and best practices.**
4. **Follow**: Use the prefix logic and structure defined in `.github/prompts/ISSUE_PROMPT.md`