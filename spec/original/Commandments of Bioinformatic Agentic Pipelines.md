*work in progress*

An agentic pipeline can be used to automate the long process of data processing and analysis. Large-scale sequencing analysis, data visualization, and data mining can be sped up from a timescale of months to weeks, or maybe days. Often when working as a computational biologist or bioinformatician our pipelines are broken up by manual steps involving inspection of data or results, choosing data-appropriate parameters or statistical tests, and other scientific judgment calls (i.e. labeling cell clusters in scRNAseq). Agents can help automate some of these processes, but to take advantage of them we need to design systems with appropriate engineering controls. Otherwise you may end up spending millions of tokens, hours of compute, and valuable human review time going too far down paths that would have never passed a "smell test" you would have intuitively being doing while working through the data "by hand" yourself without an LLM. That's where some software engineering tools come in:

### The Commandments

1. Pre-specify the analysis pipeline in a module path.
	Analysis modules are connected in known, declared ways. The agent routes within a fixed topology; it does not invent the analysis plan when run on new data. 
2. Extensive documentation and logging
	LLMs make reading and writing logs of everything you do extremely easy. That means EVERYTHING gets written down. If it's not logged or recorded somewhere it effectively didn't happen. Future agents will be able to use these logs to get up to speed and continue multi-session projects. A session begins by reading the logs and high level progress documentation. It always ends with a write up on what was accomplished, furthered, learned, or altered. Progress updates should be written to many small files with searchable, informative filenames including a date/time stamp instead of one giant file. This helps save the future agents from having to read 1000 page documents before every session. A single coordinator agent or map file might be necessary. 
3. Version control is a ledger, not an archive.
	Everything that constitutes the method lives in git and is committed _before_ it runs — code, prompts, skill definitions, module topology, gate implementations, thresholds, controlled vocabularies, environment specifications. Data, run logs, and generated figures stay out; they are content-hashed or stored in the results database and linked back by commit SHA. Every run records the SHA and whether the working tree was dirty, and a dirty tree is not a valid run. The goal is not to produce a repository at publication — that falls out for free. The goal is that every change to the method has a timestamp, an author, and a reason, so that when two runs disagree, `git diff` answers why.
	[[git-practice-agentic-pipelines]]
4. Re-use skills across sessions instead of re-writing prompts for set tasks
	Follow the "Do one thing and do it well" philosophy to help reduce maintenance and debugging needs
5. Judgment tasks performed by models are handled differently from routine code execution
	Repeated runs (>=3) are stored, compared, amalgamated
	Evaluation tests are included wherever possible after these steps (see #7)
	Disagreement or uncertainty is flagged and routed to human attention
	Log the considered set of options explored, not just the flagged set.
6. Keep the models out of the arithmetic. 
	Anything that can be code is code. The model routes, labels, decides what merits attention, and writes prose. It never computes a fold change, summary statistic, etc. 
	The model may _propose_ a statistical test with stated assumptions; code checks the assumptions against the data (normality, variance, sample size, dependence structure) and either confirms or vetoes
7. Evaluate model judgment calls 
	Evidence must exist, numbers match their source
	Consider using [[eval controls]] for high stakes steps
8. Uncertainty is reported, not automatically resolved.
	Every judgment call carries a declared confidence, and abstention is always an available answer. A module that cannot support a call must say so rather than produce the most plausible label. Low confidence, refusal, or disagreement across repeated runs halts the module at a gate and waits for human sign-off
9. Tests are performed on the pipeline outputs as stage gates
	A failed gate halts the module. It does not warn and continue.
10. Assertions are shown using the data, never trusted
	Structured output is the norm
11. Chain of provenance is maintained for all data figure outputs
12. Human judgment is solicited when needed and captured
	Every point where a person accepts, corrects, or rejects a model's call is recorded with the same rigor as the model's output. The reviewer, the timestamp, the verdict, the correction, and the reason all become part of the run's provenance.