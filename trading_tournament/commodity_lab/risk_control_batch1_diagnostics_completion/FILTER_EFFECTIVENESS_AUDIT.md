# Filter Effectiveness Audit

focus_candidate: `commodity_basket_tsmom_top2_200d_filter_v1`

filter_binding_status: `available`

## Questions

1. Did the 200d filter bind?

Yes. The diagnostics-only export found non-identical base-vs-filter weights in 39 of 157 sampled windows. The summed per-window differing-weight days were 1,062.

2. Did selected products remain above 200d SMA during the bad windows?

The risk evidence says the filter did not remove the bad windows. The worst 90d and 180d drawdowns remained the same as the base commodity rule, so the selected products either remained eligible during those bad windows or the filter shifted into exposures that did not reduce drawdown.

3. Did it produce nearly identical target/drawdown outputs to base commodity?

Nearly yes for the practical risk question. Target counts were close and 180d +300/+400/+600 counts were exactly the same as the base row in the reported risk-control packet. More importantly, the 90d and 180d worst drawdowns remained `-$680.67` and `-$718.24`.

4. Is this a natural result or possible implementation issue?

The new diagnostics indicate the filter did bind, so the result is not simply a dead filter. However, because the output did not reduce the drawdown breach, the row still needs review before it can be trusted as a risk-control mechanism. It may be a natural result of commodity wrappers staying above the 200d SMA into the drawdown window, or it may reflect a signal/timing implementation detail worth checking later.

5. Should the 200d filter be rejected, fixed, or kept under bug review?

Keep status: `filter_ineffective_or_bug_review`.

Do not promote it. Do not tune it. Do not add variants in this task.

