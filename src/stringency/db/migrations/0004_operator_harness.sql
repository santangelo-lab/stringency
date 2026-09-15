-- 2026-09-15 (ux-two-audiences 3.2): which operator harness relayed a verdict, from
-- STRINGENCY_OPERATOR, beside operator_session_ref. Additive; null for tty and web reviews
-- recorded without an operator in the environment.
ALTER TABLE reviews ADD COLUMN operator_harness TEXT;
