# Syncing with Upstream Repository

This guide outlines the steps to bring in the latest changes from the upstream repository into your local fork and update the AMP hosted instance

## Prerequisites

- Ensure you have both `origin` and `upstream` remotes configured
- Current remotes:
  - `origin`: https://romboter@github.com/Romboter/aedilebot.git (your fork)
  - `upstream`: https://github.com/olted/aedilebot.git (original repository)

## Steps to Sync with Upstream

### 1. Fetch the latest changes from upstream
```bash
git fetch upstream
```

### 2. Switch to your main branch (usually `main` or `master`)
```bash
git checkout main
```

### 3. Merge the upstream changes into your local main branch
```bash
git merge upstream/main
```

### 4. Push the updated main branch to your fork
```bash
git push origin main
```

## Troubleshooting

### If you have uncommitted changes
```bash
# Stash your changes
git stash

# Follow the sync steps above

# Restore your changes
git stash pop
```

### If there are merge conflicts
1. Resolve conflicts in the affected files
2. Stage the resolved files: `git add <filename>`
3. Complete the merge: `git commit`
4. Push to your fork: `git push origin main`

## Quick One-Liner (for clean working directory)
```bash
git fetch upstream && git checkout main && git merge upstream/main && git push origin main
```

---

**Note**: Always ensure your working directory is clean before syncing with upstream to avoid complications.


## Updating AMP instance

1. Stop the running instance using the actions buttons
2. Update
3. Start
