# notes

Session notes for the stringency engine. Commandment 2: if it is not written down it did not
happen, and future agents get up to speed from these files rather than from a thousand-page log.

## Convention

- One file per session, named `YYYY-MM-DD-hhmm-<slug>.md` (the time the session ended, 24-hour,
  local). The slug says what the session was about in two to four words.
- Small files. If a session covered two unrelated things, write two files.
- Every note has the same five sections: **Goal**, **Done**, **Learned**, **Altered** (anything
  changed that was not planned: a contract, a convention, a decision), **Open** (what is left,
  and what the next session should do first). Add **Verify** when there is a command that proves
  the work.
- Link to commits by short SHA and to decisions by their line in `spec/DECISIONS.md`. Do not
  paste code or tool output into a note; point at the file.
- After writing a note, add one line for it to `INDEX.md` and update the **Current state** block
  there. `INDEX.md` is the map; it holds pointers, never content.

## For an agent starting a session

1. Read `INDEX.md` (short) and the most recent note it lists.
2. Read older notes only when the index says they matter for the task.
3. Work. Record design-silent choices in `spec/DECISIONS.md` as you go.
4. End the session by writing the note and updating `INDEX.md`, then commit both with the work.
