---
name: issue-fix
description: Triage and fix GitHub issues end-to-end. Fetches the issue, explores relevant code, plans the fix, implements with TDD, and verifies. Use when user says "fix issue #N", "work on this issue", or references a GitHub issue number.
---

# Issue Fix Skill
**Usage:** /issue-fix <issue-number>

**Trigger this skill when:**
- User says "fix issue #N", "work on issue #N"
- User references a GitHub issue number
- User says "work on this issue" with a number
- Automated pipeline triggers issue resolution

**Skip for:** Known bugs with clear cause (use bug-fix), PR review (use pr-review), feature requests without issue (use code-implementation)

---

## Phase 1: Issue Intake

### Step 1.1: Fetch Issue Details

```bash
gh issue view <number> --json title,body,labels,assignees,comments
```

### Step 1.2: Triage

Classify the issue:

| Type | Indicators | Next Action |
|------|-----------|-------------|
| **Bug report** | Error message, "not working", reproduction steps | Investigate root cause |
| **Feature request** | "Add", "implement", "support" | Plan implementation |
| **Unclear** | Vague description, no reproduction steps | Ask user for clarification |

### Step 1.3: Create Working Branch

```bash
git checkout -b fix/<issue-number>-<short-description> main
```

---

## Phase 2: Investigate

### Step 2.1: Locate Relevant Code

Fire an `explore` sub-agent to find:
- Files mentioned in the issue
- Code related to the error or feature area
- Existing tests for the affected area
- Recent changes that may have caused the issue

### Step 2.2: Root Cause Analysis (for bugs)

Deploy `root-cause-hunter` sub-agent with context packet:
- Issue title and body
- Affected file paths from Step 2.1
- Error messages or stack traces from the issue

### Step 2.3: Scope Analysis (for features)

Determine:
- What files need to change
- What new files are needed
- What tests must be written
- What existing tests might break

---

## Phase 3: Plan the Fix

### Fix Plan Template

```markdown
## Fix Plan: Issue #<number>

### Summary
[One sentence: what this fix does]

### Root Cause (bugs) / Approach (features)
[Why the issue exists OR how the feature will be implemented]

### Files to Modify
- `path/to/file1` — [what changes]
- `path/to/file2` — [what changes]

### New Files
- `path/to/new_file` — [purpose]

### Tests
- `tests/path/test_file.py::test_name` — [what it verifies]

### Success Criteria
- [ ] [Specific testable outcome]
- [ ] [Specific testable outcome]
- [ ] All existing tests still pass
```

### Step 3.1: Present Plan

Show the plan to the user and wait for approval before proceeding.

---

## Phase 4: Implement (TDD)

### Step 4.1: Write Failing Tests

Write tests that define the expected behavior:
- For bugs: test that reproduces the bug
- For features: test that defines the new behavior

### Step 4.2: Run Tests to Confirm Failure

```bash
python -m pytest tests/path/test_file.py::test_name -v
```

Expected: FAIL

### Step 4.3: Implement the Fix

Make the minimal code changes to pass the tests.

### Step 4.4: Run Full Test Suite

```bash
python -m pytest tests/ -v --tb=short
```

Expected: ALL PASS (including new tests)

---

## Phase 5: Verify & Present

### Step 5.1: Final Verification

- [ ] New tests pass
- [ ] All existing tests pass
- [ ] No lint/type errors
- [ ] Changes are minimal and focused

### Step 5.2: Commit

```bash
git add <specific-files>
git commit -m "fix(component): resolve issue #<number> — <short description>"
```

### Step 5.3: Report to User

```markdown
## Issue #<number> — Fixed

### Changes Made
- `file1:line` — [what changed]
- `file2:line` — [what changed]

### Tests Added
- `test_name` — [what it verifies]

### Verification
- All tests passing (N/N)
- No regressions detected

### Next Steps
- Push and open PR? (use /gitpush)
- Close the issue?
```

---

## Quality Guidelines

**ALWAYS:**
- Read the full issue before acting
- Create a branch before making changes
- Write tests before implementation
- Run the full test suite, not just new tests
- Present a plan before implementing

**NEVER:**
- Start coding without reading the issue
- Skip the planning phase
- Commit without running tests
- Close the issue without user confirmation
- Mix fixes for multiple issues in one branch
