# History And Regime Coverage Review

Acquired data coverage:

| symbol | rows | first date | last date | quality |
|---|---:|---|---|---|
| DBMF | 1,780 | 2019-05-08 | 2026-06-05 | pass |
| KMLM | 1,383 | 2020-12-02 | 2026-06-05 | pass |

Common windows:

- DBMF/KMLM overlap: 2020-12-02 to 2026-06-05.
- Overlap with cached SPY/BIL: 2020-12-02 to 2026-05-29.

## Review Questions

1. Is this enough for research_sample?

Yes, conditionally. The overlap is long enough to run a limited research_sample after warmups, but every result must be labeled short-history and fund-wrapper proxy evidence.

2. Is this enough for candidate_exhaustive?

Not automatically. Candidate_exhaustive should require either strong research_sample evidence with explicit short-history labeling or a separate gate accepting limited-inception evidence.

3. Does it cover 2022 inflation/rate regime?

Yes. The common overlap includes 2022.

4. Does it cover COVID/post-COVID?

It covers post-COVID and late-2020 onward. DBMF covers part of the 2020 COVID crash period, but KMLM does not because its wrapper history starts in December 2020.

5. Does it cover 2008?

No.

6. Does it cover enough crisis regimes for strong claims?

No. It lacks 2008 and has only one meaningful inflation/rate shock period.

7. Is short-history risk high?

Yes. KMLM creates the effective common-history start and limits confidence.

8. Should results be labeled limited-inception / short-history?

Yes. This label is required.

9. Should candidate_exhaustive be blocked until more history or explicitly labeled?

Candidate_exhaustive should be blocked unless the project explicitly accepts short-history-labeled candidate_exhaustive. Research_sample may proceed with the label.

## Decision

History coverage is sufficient for a cautious research_sample prompt only. It is not sufficient for strong claims, paper-forward readiness, or direct managed-futures conclusions.
