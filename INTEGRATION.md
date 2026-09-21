# Integration result

Branch: `integration/upstream-plus-nigel-fixes`.
Base: local `origin/main`, `641f7c810449d9af5c21b0a5ee33b29b192b4117`.
The two approved changes are integrated; validation is partial, not a clean full-suite receipt.

## Included and excluded

| Fix | Decision | Reason |
| --- | --- | --- |
| strict-tool-call-content | Included, `46655946aa` | Normalizes empty/whitespace assistant text beside tool calls to null at both outgoing boundaries, preserving stored history and deterministic request serialization. |
| cron-github-auth-scrub | Test only, `cfc0a56fd8` | Upstream already scrubs all allowlisted GitHub auth-header blocks; nine added test lines cover multiple commands with different quoting and token syntax. |
| oneshot-skills | Excluded | Upstream forwards skills through its consolidated oneshot path and supports partial success; importing the old implementation would regress that behavior. |
| credential-pool | Excluded, unresolved | A newer OAuth refresh timestamp does not establish quota recovery, and the old rule could clear a cooldown retained after a failed quota probe. A human must decide semantics and scope. |

I read all four requested sibling reports. Their reasoning supports these decisions.
The credential analysis does **not** establish that every original symptom is fixed:
read accessors can retain stale status metadata, `peek()` can return an unvalidated
current entry, and availability/restore gates can bypass early quota-recovery probes.
Those findings warrant a separate investigation; no credential-pool port or resolution
was attempted here. The original requested credential commit was two files, not the
larger series described in that sibling's task, another scope question for a human.

## Integration method and scope checks

Used local cherry-picks with provenance trailers, preserving Nigel's authorship:

```sh
GIT_NO_LAZY_FETCH=1 git cherry-pick -x 268c5a2264
GIT_NO_LAZY_FETCH=1 git cherry-pick -x 5076d2f3d0a
```

Neither produced a content conflict. The first command initially failed because the
sandbox exposed the shared Git index as read-only; its approved elevated retry
succeeded. The second also used approved elevated access for Git metadata.
Inspection confirmed that `5076d2f3d0a` itself contains only the nine-line test
addition, so cherry-picking that entire commit imported no production code.

No sibling report commits were imported. No sibling worktrees were modified, no
fetch or push was run, and no dependency files were edited. Git inspection and
cherry-picks used `GIT_NO_LAZY_FETCH=1` to prevent implicit object retrieval.
The final integration diff changes only two agent production files and three test
files, plus this report. `tools/`, `pyproject.toml`, and `uv.lock` remain identical
to the base. `git diff --check 641f7c8104 HEAD` passed before adding this report.

## Test receipts

All commands ran from this worktree with the shared executable explicitly required
by TASK.md, overriding the general repository test-runner rule. No dependencies
were installed and no test implementation was changed to make validation pass.
Output redirections below are part of the actual commands.

### Required strict-content tests

```sh
/home/lovely/Work/hermes-agent/.venv/bin/pytest tests/agent/transports/test_chat_completions_empty_tool_call_content.py tests/agent/test_partial_stream_finish_reason.py -q
```

An initial invocation mistakenly followed the failed sandbox cherry-pick, before
the new test file existed: exit 4, with the verbatim summary:

```text
no tests ran in 0.00s
```

After the successful cherry-pick, the same command reached 28 passing progress
dots and stalled. I interrupted it (exit 130); no pytest summary was emitted.
I repeated it with a diagnostic traceback timer:

```sh
/home/lovely/Work/hermes-agent/.venv/bin/pytest tests/agent/transports/test_chat_completions_empty_tool_call_content.py tests/agent/test_partial_stream_finish_reason.py -q -o faulthandler_timeout=30 > /tmp/hermes-integration-focused.log 2>&1
```

This again stalled after 28 progress dots. The timer emitted `Timeout (0:00:30)!`;
the main thread was inside `asyncio.run` in
`agent/vision_message_prep.py:114::_describe_image_for_anthropic_fallback`, called
by `test_multimodal_assistant_content_not_touched` at line 844. I interrupted the
diagnostic run (exit 130); it also emitted no final pytest summary. This identifies
the waiting path, not the underlying cause or whether the base behaves identically.

Narrowed by excluding exactly that one stalled case:

```sh
/home/lovely/Work/hermes-agent/.venv/bin/pytest tests/agent/transports/test_chat_completions_empty_tool_call_content.py tests/agent/test_partial_stream_finish_reason.py -q -k 'not test_multimodal_assistant_content_not_touched' > /tmp/hermes-integration-focused-narrow.log 2>&1
```

```text
35 passed, 1 deselected in 4.25s
```

### Required cron tests

```sh
/home/lovely/Work/hermes-agent/.venv/bin/pytest tests/tools/test_cronjob_tools.py -q
```

```text
75 passed in 1.95s
```

### Requested broad regression sweep

```sh
/home/lovely/Work/hermes-agent/.venv/bin/pytest tests/agent tests/tools tests/hermes_cli -q > /tmp/hermes-integration-regression.log 2>&1
```

```text
6 skipped, 9 deselected, 7 warnings, 1 error in 39.63s
```

Exit 2 during collection: `tests/tools/test_slack_send_message_media.py` imports
the Slack adapter, which cannot import `aiohttp` from the shared environment.
No tests executed in this sweep. A later interrupt request encountered the already
completed command; the recorded result is its collection failure.

### Narrowed regression sweep

Covered all agent transports, strict API validation, cron prompt handling, and the
upstream oneshot skill/loading and dispatch tests:

```sh
/home/lovely/Work/hermes-agent/.venv/bin/pytest tests/agent/transports tests/agent/test_strict_api_validation.py tests/tools/test_cronjob_tools.py tests/hermes_cli/test_oneshot_skills.py tests/hermes_cli/test_tui_resume_flow.py -q > /tmp/hermes-integration-narrow.log 2>&1
```

```text
535 passed in 11.50s
```

These passing runs overlap; their counts must not be added as unique coverage.

## Surprises and required human review

- No evidence contradicted the include/exclude decisions. However, I could not
  reproduce the table's reported **36-test pass**: 35 pass here, and the multimodal
  case stalls in the vision fallback. Diagnose that case and rerun the full required
  pair before treating the focused validation as complete.
- The broad sweep is not green: restore the missing test dependency in an approved
  environment, rerun it, and investigate any further collection or execution errors.
  Its initial collection failure says nothing about the unexecuted tests.
- Review the null-content behavior against the actual strict provider/gateway used
  in production. These local tests exercise serialization and mocked agent paths;
  no successful live provider round trip or production prompt-cache measurement
  was performed.
- Keep the credential-pool decision separate: determine whether automatic token
  refresh may reopen exhausted quota, examine availability/restore gates, and
  confirm whether the requested scope is the two-file commit or its ancestor series.
  No production auth store, account quota, or incident logs were examined here.

The branch contains the approved surviving changes, but the missing broad-suite
receipt and stalled focused case remain explicit review blockers to full trust.
