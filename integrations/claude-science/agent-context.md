This project is driven by stringency, a command-line engine that gates each analysis step and
records a trace. Load the `stringency-operator` skill before acting; it holds the rules and the
run loop. In brief:

- The engine is installed at /usr/local/lib/stringency/current/bin on the lab workstation. If that
  workstation is a registered compute provider, run every stringency command there through the
  compute connection (skill mode B); a sandbox cannot start containers. If the engine is missing,
  stop and tell the user rather than building it yourself.
- In every cell that calls stringency, export STRINGENCY_OPERATOR=claude-science,
  STRINGENCY_OPERATOR_VERSION=<app version or unknown>, and STRINGENCY_SESSION_REF=<your frame id>.
- Exit code 10 is a hold. Print the hold id and message verbatim and stop; only the project owner
  resolves holds, at their own terminal. Never accept, override, reject, or defer one.
- Never write under prov/ or edit method/, stringency.yml, objective.yml, design.yml, inputs.yml.
- Run module scripts only as the ticket's job spec describes, inside the named container image,
  with the step directory, input directories, and script directory bound.
- Answer a judgment dispatch (exit 20) with one fresh delegate per request file, giving it only
  the file path. If no delegate tool exists, answer each in its own fresh cell and say so.
- When a submit reports the run completed, do not call run again; call deliver and save
  coverage.md, methods.md, and index.json as artifacts.
