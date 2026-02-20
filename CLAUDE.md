# CLAUDE.md

## Project Standards

- **Language:** Use the primary language and version detected in the workspace
- **Issues:** Use `.github/prompts/ISSUE_PROMPT.md` for all issue creation and task documentation tasks
- **Commits:** Use `.github/prompts/COMMIT_PROMPT.md` for all commit message formatting

## Issue Tracking

When asked to draft or create a GitHub issue:

1. **Context Check**: Identify the primary programming language and framework of the current project (e.g., Python/FastAPI for backend, React/TS for frontend).
2. **Read**: Load instructions from `.github/prompts/ISSUE_PROMPT.md`.
3. **Implementation**: In the "Proposed Implementation" section, provide code snippets or logic suggestions using the **current project's language and best practices.**
4. **Follow**: Use the prefix logic and structure defined in `.github/prompts/ISSUE_PROMPT.md`
