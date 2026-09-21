# Oneshot skills: already implemented upstream

Base examined: `641f7c810449d9af5c21b0a5ee33b29b192b4117`.
Requested cherry-pick: Nigel's `e12a5feaa7f557de0ca4432ef97ff92122e46ccb`
(`fix(cli): honor skills in oneshot mode`).

## Conflicts and decision

Attempted `git cherry-pick e12a5feaa7`. All three files conflicted:

- `hermes_cli/main.py`: upstream consolidated both entry paths into
  `_run_oneshot_from_args`; it already forwards `args.skills` through
  `_run_and_exit_oneshot` to `run_oneshot`.
- `hermes_cli/oneshot.py`: upstream already normalizes and deduplicates skill
  names, loads their instructions, and passes the result as the agent's
  `ephemeral_system_prompt`. Its current helper returns a prompt rather than
  the old patch's tuple. Upstream also supports partial success: valid skills
  load with a warning about missing ones; all-missing requests raise an error.
  Applying the old implementation would regress that behavior.
- `tests/hermes_cli/test_tui_resume_flow.py`: upstream reorganized the old
  tests and changed the oneshot interfaces (including agent result tuples and
  the hard-exit wrapper). The historical test additions cannot be applied
  unchanged. Upstream has dedicated normalization/loading coverage in
  `tests/hermes_cli/test_oneshot_skills.py`.

Restored these three files to their upstream contents and used
`git cherry-pick --skip`. No production or test changes are needed. The only
committed change is this report; no empty or misleading fix commit was made.

## Implementation evidence

- `hermes_cli/main.py:3062`: shared dispatch forwards `skills`.
- `hermes_cli/main.py:158`: exit wrapper forwards `skills` to `run_oneshot`.
- `hermes_cli/oneshot.py:305`: `run_oneshot` forwards `skills` to `_run_agent`.
- `hermes_cli/oneshot.py:568`: `_run_agent` loads the requested skill prompt.
- `hermes_cli/oneshot.py:588`: that prompt reaches `AIAgent` through
  `ephemeral_system_prompt`.

## Validation

Used the interpreter explicitly required by TASK.md, overriding the general
repository test-runner instruction:

```text
PYTHONDONTWRITEBYTECODE=1 /home/lovely/Work/hermes-agent/.venv/bin/pytest tests/hermes_cli/test_tui_resume_flow.py tests/hermes_cli/test_oneshot_skills.py -q
13 passed in 1.93s
```

This runs the current version of the requested test file and the dedicated
upstream skill tests. It does not claim that the obsolete patch's two new
tests ran unchanged, or that a live model request was exercised.

A history search encountered an unavailable object in this partial clone and
Git attempted automatic retrieval, which failed on DNS resolution. No history
download was retried; the decision rests on the available current source and
passing tests. No explicit fetch, push, rebase, branch switch, or dependency
file edit was performed.

**Still needed? No. Current upstream already implements the fix's intent.**
