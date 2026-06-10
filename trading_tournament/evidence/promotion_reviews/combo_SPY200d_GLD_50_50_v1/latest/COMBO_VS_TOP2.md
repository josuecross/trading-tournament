# Combo Versus Asset Class TSMOM Top2

## Summary

`asset_class_tsmom_top2_v1` remains a serious challenger. It narrowly led the original final_score, but `combo_SPY200d_GLD_50_50_v1` is the practical drawdown-aware leader under score v2.

## Comparison

| Metric | Combo | Top2 | Interpretation |
|---|---:|---:|---|
| original final_score | 66.77 | 67.05 | Top2 narrowly leads original score |
| balanced_drawdown_aware_score_v2 | 101.59 | 6.57 | Combo leads by risk-aware scoring |
| 90d +300 | 20.9% | 21.5% | Top2 slightly higher |
| 90d +400 | 9.2% | 9.4% | Top2 slightly higher |
| 90d stop-hit rate | 0.0% | 0.0% | Tie |
| 90d worst drawdown | -$452.23 | -$579.66 | Combo materially better |
| 180d +300 | 48.1% | 46.8% | Combo slightly higher |
| 180d +400 | 31.5% | 32.2% | Top2 slightly higher |
| 180d stop-hit rate | 0.0% | 1.3% | Combo better |
| 180d worst drawdown | -$516.49 | -$655.41 | Combo better |
| stress degradation | 22.03 | 6.01 | Top2 better |

## Duplicate Or Role Risk

Top2 is an asset-class momentum strategy. The combo is a fixed combination of the existing SPY trend model and GLD buy-hold. They are not duplicates, but both are trying to use GLD/equity diversification to improve the challenge tradeoff.

## Conclusion

Top2 remains a promotion-review candidate in research evidence, but combo is the cleaner practical challenger for a paper-forward observation plan review because it uses less drawdown budget and has zero standard stop hits across the full horizon set.

