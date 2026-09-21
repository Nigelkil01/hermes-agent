# Cron GitHub auth scrub: blocked

Branch: `wip/cron-github-auth-scrub`
Base: `641f7c810449d9af5c21b0a5ee33b29b192b4117`
Requested commit: `2255fd03c3` (`fork/fix/cron-github-auth-scrub`).

## What happened

The local repository is a partial clone with missing objects. Inspecting the
requested commit with `git show --stat 2255fd03c3` caused Git to attempt an
implicit fetch from its promisor remote. That failed with a DNS error and:

```text
fatal: could not fetch 6c5821e863e0ed7939ec0ac8bb789dfd75647d5f from promisor remote
```

I disabled lazy fetching for subsequent Git operations. The required cherry-pick
initially encountered a sandbox restriction creating this worktree's index lock.
After retrying with permission to write Git metadata, the command
`GIT_NO_LAZY_FETCH=1 git cherry-pick 2255fd03c3` failed with:

```text
warning: lazy fetching disabled; some objects may not be available
fatal: could not fetch 4e46523a98396c63b8b416381c254f32e2b5d906 from promisor remote
```

## Decision and remaining work

No conflict resolution was reached. The cherry-pick made no source changes and
left no cherry-pick in progress; Git reported a clean working tree at the base
commit before this report was written. I stopped because fetching is expressly
forbidden by TASK.md, and reconstructing the unavailable patch would not preserve
the requested contributor commit confidently.

The missing Git objects must be made available by the repository owner before
the cherry-pick can proceed. No explicit fetch, push, checkout, or rebase was run;
neither dependency file was modified.

## Tests and necessity

Tests were not run: the fix could not be applied, so there is no test summary
line for the requested fix. Whether upstream already implements the complete
fix remains undetermined. Only this blocker report is committed locally.
