# Git Commit Standards

## Format

`<type>(<scope>): <description>` (Conventional Commits).

## Types

`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.

## Logic

1. Run `git log -n 5` to confirm existing scope naming conventions.
2. Use the imperative mood (e.g., "add connection wizard").
3. **Issue Linking**: If the change resolves an open issue, append `(fixes #ID)` or `(closes #ID)` to the end of the description.
4. **Verification**: Check `.github/prompts/ISSUE_PROMPT.md` to ensure the commit fulfills the requirements defined in the task.

## Example

`feat(ui): connection wizard with test flow (fixes #12)`
