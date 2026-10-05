# Model evaluation (synthetic-only, draft)

Status: draft, pending clinical review. Decision support only.
All rows are synthetic from `ml/synthetic.py` (seed 123); no clinical validity.

Model: `synthetic-v0.1` n=3000
AUC (ovr): 0.963
Recall L1-2: 0.913 (L1 0.856, L2 0.949)
Cohen kappa: 0.881
Within ±1 accuracy: 0.997

## Subgroup recall by age band

- infant_<2: n=150 recall=0.9
- child_2_17: n=450 recall=0.918
- adult_18_64: n=1800 recall=0.918
- older_65+: n=600 recall=0.887
