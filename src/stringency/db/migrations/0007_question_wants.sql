-- 2026-10-29 (PLAN L139): the quantity that would answer a question, in the operator's words,
-- filed with the question (`ask --wants`) so the fit of a tool to the question is recorded
-- before the route. Null on a question filed without it and on every question filed before.
-- What a step's output is (`call`/`exec --gives`) goes on the step's `created` event payload.
ALTER TABLE questions ADD COLUMN wants TEXT;
