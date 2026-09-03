You are labelling groups of numeric observations from their summary statistics.

Each row of the table below is one group. Columns: n_rows, n_units, mean_value, sd_value, top_unit.

{{ evidence_table }}

Assign each of these items a label: {{ items | join(", ") }}.

Choose one label per group from this vocabulary only:
{% for v in vocabulary %}- {{ v }}
{% endfor %}
Rules. Cite the table cells you used as evidence references (table "summary", row = group, column, value copied exactly). Any number you write in the rationale must appear among your cited values. If the statistics do not support a label, abstain: set abstain to true, label to null, and confidence to "abstain".
