# Symptom extraction evaluation (draft lexicon)

Status: draft, needs native-speaker review. Decision support only, not diagnosis.

- Test set: `backend/tests/data/utterances.csv` (120 utterances: English, Hindi Devanagari, Hindi Romanised, Marathi, code-switched; includes negation and duration cases).
- Lexicon: `docs/vocabulary.csv` (150 canonical symptoms; draft translations).
- Method: exact substring match first, then fuzzy token match (ratio ≥ 0.82); negation via surrounding negation words ("no", "nahi", "na"); duration via number+unit ("3 days", "do din").
- Results (non-negated candidates vs expected): TP=118 FP=17 FN=14, precision=0.874, recall=0.894.
- Limits: lexicon is draft; fuzzy matching over-generates on short tokens (17 FPs); negation scope is chunk-local and misses long-distance negation; duration parsing covers days/weeks/months only. Native-speaker review required before any clinical use.
- Serving: POST /visits/{id}/symptoms/extract returns candidates with confidence and never saves; POST /visits/{id}/symptoms saves only after human confirmation.
