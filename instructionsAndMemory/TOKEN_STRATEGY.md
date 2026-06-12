# TOKEN_STRATEGY.md

> Internal optimization guide. Keep this updated to minimize token waste across sessions.

---

## Frequently Accessed Files (Hot)

> Read these often; keep mental model current.

| File | Why It's Hot |
|------|-------------|
|      |             |

## Stable Files (Cold)

> Do not re-read unless a specific change is needed.

| File | Reason It's Stable |
|------|-------------------|
|      |                   |

## Files to Never Read

> Large generated, compiled, or vendor files with no value to Claude.

```
node_modules/
dist/
build/
coverage/
.cache/
.next/
.nuxt/
target/
venv/
.terraform/
terraform.tfstate*
logs/
*.log
*.lock        # unless debugging dependency issues
```

## Token-Saving Rules

1. Read `NEXT_SESSION.md` before any source file.
2. Use `CODE_INDEX.md` to locate files — don't scan directories.
3. Never read a file to answer a question that memory files already cover.
4. When pasting code for review, paste only the relevant function or block.
5. Prefer file paths + line references over full file dumps.
6. Summarize completed work into `SESSION_LOG.md` instead of keeping raw chat.

## Large Files to Summarize (not read in full)

| File | Strategy |
|------|----------|
|      |          |
