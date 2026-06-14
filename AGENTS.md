# Repository Instructions

## Commit Hygiene

- Keep commits scoped to one behavioral change. Do not bundle separate features, bug fixes, formatting-only changes, or experiments into the same commit.
- Before committing, inspect the staged diff and split it when the change contains distinct user-visible outcomes. For example, Telegram rich formatting and Telegram streaming should be separate commits.
- Use the versioning prefix convention from `app-data/bump-version.sh`: `[Feature]`, `[Improvement]`, or `[Bugfix]`.
- Keep automatic changelog/version/formatting commits separate from functional commits unless the user explicitly asks to combine them.
- If an exploratory change is abandoned or reverted before commit, remove the related code and documentation before committing the remaining work.
