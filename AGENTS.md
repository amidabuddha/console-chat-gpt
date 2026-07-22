# Repository Instructions

## Commit Hygiene

- Keep commits scoped to one behavioral change. Do not bundle separate features, bug fixes, formatting-only changes, or experiments into the same commit.
- Before committing, inspect the staged diff and split it when the change contains distinct user-visible outcomes. For example, Telegram rich formatting and Telegram streaming should be separate commits.
- Use the versioning prefix convention from `app-data/bump-version.sh`: `[Feature]`, `[Improvement]`, or `[Bugfix]`.
- Keep automatic changelog/version/formatting commits separate from functional commits unless the user explicitly asks to combine them.
- If an exploratory change is abandoned or reverted before commit, remove the related code and documentation before committing the remaining work.

## Push Workflow

- Every push to `main` triggers `.github/workflows/formatting.yml`, which may push a follow-up commit named `Formatting and updating the changelog.` that updates formatting, `CHANGELOG.md`, and `app-data/version.toml`.
- Before pushing to `main`, fetch `origin/main` and rebase local commits if the remote branch has advanced. Never force-push merely to bypass the automation commit.
- After pushing to `main`, wait for the formatting workflow to finish, then fetch and fast-forward the local branch so the checkout includes the generated commit before starting or pushing more work.
