# Codex CLI as a harness

The survey of OpenAI's Codex CLI on the lab workstation (H1 of `PLAN.md` L34), what each of
stringency's two harness roles (design 10.1) can be with it, and the appendix a Codex session
follows beside the harness-neutral operator skill. Surveyed 2026-10-21 on codex-cli 0.163.0,
logged in with the lab's ChatGPT team plan (`codex login status`: "Logged in using ChatGPT").

## What was found

- `codex exec [PROMPT]` runs one turn headless. `--json` prints JSON Lines events
  (`thread.started`, `turn.started`, `item.completed` with the agent's message, `turn.completed`
  with `usage.input_tokens` and `output_tokens`); `--output-schema <file>` constrains the final
  message to a JSON Schema; `-o <file>` writes the last message to a file; `--ephemeral` keeps
  no session on disk; `-s read-only` is the sandbox (also `workspace-write`,
  `danger-full-access`); `-c approval_policy="never"` stops it waiting for an approval a headless
  run cannot give; `-C <dir>` sets the working root; `--skip-git-repo-check` is needed outside a
  repository. With stdin piped it reads stdin as additional input and blocks until EOF, so a
  caller closes stdin or puts the prompt there.
- A session exports `CODEX_VERSION`, `CODEX_THREAD_ID`, `CODEX_SESSION_ID`,
  `CODEX_TOOL_CALL_ID`, `CODEX_CI` and `CODEX_SANDBOX_NETWORK_DISABLED` into the commands it
  runs. The engine reads the first three as the operator's harness, version and session
  reference when `STRINGENCY_OPERATOR*` is unset (`operator_id.py`, engine 0.2.32).
- The model reports itself as `gpt-6` and lists `collaboration.spawn_agent`,
  `collaboration.wait_agent` and `collaboration.send_message` among its tools: the interactive
  agent can delegate (feature `multi_agent`, stable). A delegate cannot be restricted to one
  file any more than a Claude Science delegate can, so isolation stays `as_reported`.
- `codex sandbox <command>` runs a command under the Linux sandbox; `codex mcp` manages MCP
  servers; `codex doctor` reports the install (standalone, under `~/.codex/packages`).
- The event stream does not name the model; only the usage. A judgment answered by
  `codex exec` therefore records `model_resolved: unknown` unless the project's `judgment.model`
  is set and passed with `-m`, in which case it is the requested model and still recorded as
  unknown in the resolved column (design 10.2: never guessed).

## The two roles

**Operator harness.** A Codex session drives the CLI as Claude Code does: a shell, the engine on
PATH, the project directory as its working root. Identity comes from the session's own
variables; `STRINGENCY_OPERATOR=codex` may be set but need not be. Judgment dispatches (exit 20)
are answered with one `collaboration.spawn_agent` per request file, given only the file path,
exactly as the operator skill's section 7 says for any delegate; with no delegate the session
answers each in a fresh `codex exec` and says so in `reported.agent`.

**Judgment harness, by command.** The `command` adapter (engine 0.2.32) runs a configured
command once per replicate in a fresh process, the prompt on stdin, the module's schema in a
file, and reads the response file. For Codex:

```
stringency init <project> ... --judgment-harness command --judgment-command \
  'codex exec --ephemeral --skip-git-repo-check -s read-only -c approval_policy="never" --json --output-schema {schema} -o {response} -C {dir} -'
```

The trailing `-` reads the prompt from stdin. Each replicate is a fresh thread by construction,
so the three replicates never share a context; the invocation row carries `via: command`,
`isolation: as_reported`, the token counts from `turn.completed`, and the response text. The
egress assessment counts the harness as class 3 (the prompt goes to OpenAI). A method's controls
run through it like any other harness; the mock stays the test harness.

## The operator appendix for Codex

Read beside the `stringency-operator` skill; where the skill says "mode A" or "mode B", a Codex
session is mode A with the engine on this machine.

1. Find the engine: `command -v stringency || ls <prefix>/current/bin/stringency`, then
   `stringency probe --method <project>/method --no-hash`. Stop on `not ready`.
2. Identify yourself: nothing to export; the engine reads `CODEX_VERSION` and
   `CODEX_THREAD_ID`. Set `STRINGENCY_OPERATOR=codex` only if the engine is older than 0.2.32.
3. Holds: relay by section 6 of the skill; a chat answer is recorded with `review --attest`
   and needs `STRINGENCY_SESSION_REF`, which the engine takes from `CODEX_THREAD_ID`.
4. Dispatch: one `collaboration.spawn_agent` per `req_N.json`, the file path only; the delegate
   reads the file, answers the schema, copies the nonce, fills `reported` (`model`, `agent`:
   "codex subagent", `tools`, `saw_conversation: false`) and returns the JSON. Assemble the
   document and file it with `stringency run --responses - --json`; `--check` first.
5. Conformance: `uv run python integrations/conformance.py --harness codex --skill
   integrations/claude-science/stringency-operator/SKILL.md --skill integrations/codex/README.md`
   enumerates `tests/shared/dispatch.json` and `holds.json` against the skill with this appendix
   and the engine's reader; a harness enters `compat/known-good.yml` with a passing run.

## Not done here

The Qwen3 evaluation (`judge-sources-plan.md` S2) needs a local model served on this machine's
GPU and the Lyons re-judgment run as sibling projects under both harnesses; its "competent" is
the owner's definition after this survey.
