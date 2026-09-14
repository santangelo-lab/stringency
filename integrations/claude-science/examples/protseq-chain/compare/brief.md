The data for this project is the filtered table that my toy-process project delivered:
/data/lab/projects/2026-09_stringency-exit_jrrose5/process/toy-process/deliver/01M2GH5BY478331H517CV7BK1Z/01_filter.object.csv
It has the same shape as the original measurements: each row is one measurement with a row id,
the group it came from (A, B, or C), the unit it was measured on, and a value. Each unit belongs
to exactly one group and was measured several times. The file
/data/lab/projects/2026-09_stringency-exit_jrrose5/data/samples.csv lists every unit and its
group.

The unit is the independent replicate; the rows within a unit are repeated measurements.

I want to know whether the values differ between group A and group B. I want two things out of
this project: the comparison table for that contrast, and the group labels.
