# Cron GitHub auth scrub: completed

Branch: `wip/cron-github-auth-scrub`
Upstream base: `641f7c810449d9af5c21b0a5ee33b29b192b4117`
Requested commit: `2255fd03c380bd927217886c8f395c7717cd0c5e`
Local cherry-pick: `5076d2f3d0` (Nigelkil01's authorship preserved).

## Outcome and conflict resolution

The fix's production behavior is already present upstream. Commit
`70411a6152024ecb061972e778f900289c7ef046` replaced the first-match scrub with
`re.sub` to scrub every allowlisted GitHub auth-header curl block. The current
implementation lives in `tools/cronjob_prompt_scan.py::_strip_cron_safe_constructs`,
used by both the strict prompt scanner and the skill-assembled scanner. Upstream
also has regression coverage for heterogeneous GitHub blocks and mixed prompts
containing an arbitrary-host exfiltration command.

The cherry-pick conflicted in `tools/cronjob_tools.py` because upstream had
extracted the scanner and refactored the surrounding tool code. I retained that
file exactly as it was on the base, preserving the current scanner and its newer
host/separator restrictions. Reintroducing May's scanner would duplicate code and
lose upstream hardening. The test file merged automatically; I retained Nigel's
bundled regression test, which verifies multiple GitHub commands with differing
quoting and `${GITHUB_TOKEN}` syntax. The resulting cherry-pick changes only that
test file (9 added lines). No production fix is still needed.

## Validation

Ran the exact shared interpreter specified by TASK.md:

```text
/home/lovely/Work/hermes-agent/.venv/bin/pytest tests/tools/test_cronjob_tools.py -q
75 passed in 2.89s
```

This includes the bundled regression test against unchanged upstream production
code, as well as the existing arbitrary-host blocking tests.

## Previous blocker and ground rules

The earlier attempt stopped on missing partial-clone objects. After the user
reported supplying all objects, the retry succeeded with `GIT_NO_LAZY_FETCH=1`.
No fetch, push, branch checkout, or rebase was performed during this retry.
Only this worktree's files and required Git metadata were changed; neither
`pyproject.toml` nor `uv.lock` was modified. All commits are local.
