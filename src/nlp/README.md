# src/nlp — Legacy NLP Pipeline (Jupytext exports)

**Status: Legacy** — superseded by N24 unified pipeline.

These files are Jupytext `.py` exports from early NLP development notebooks (week 4).
They contain notebook-style code (flat scripts, training loops, hard-coded output paths
pointing to `../../outputs/week4/`) and are not importable as production modules.

---

## Files

| File | Source notebook | Description |
|---|---|---|
| `sentiment.py` | N20 / week-4 RoBERTa | Fine-tuning loop for RoBERTa-base sentiment (positive/neutral/negative); 87.5% test accuracy on 530 F1 radio messages |
| `ner.py` | N22 / week-4 BERT-large | Custom NER training with BERT-large-conll03; BIO-tagging for F1 entities (ACTION, SITUATION, INCIDENT, PIT_CALL, etc.) |
| `radio_classifier.py` | N21 / week-4 RoBERTa | SetFit intent classification (ORDER, INFORMATION, QUESTION, WARNING, STRATEGY, PROBLEM) |
| `pipeline.py` | N06 / week-4 model merging | Integrated pipeline combining sentiment + intent + NER into a structured JSON output; uses legacy model paths |

---

## Current production pipeline

Use the unified pipeline developed in N24:

```python
# Active pipeline (N24) — not in src/nlp/, lives in the notebook
from notebooks.agents import ...  # see N24_nlp_pipeline.ipynb
```

The `src/nlp/pipeline.py` wrapper for N24 is planned but not yet extracted (deferred to post-notebook src/ pass).

---

## Developed in

- [`notebooks/nlp/N20_bert_sentiment.ipynb`](../../notebooks/nlp/N20_bert_sentiment.ipynb)
- [`notebooks/nlp/N21_radio_intent.ipynb`](../../notebooks/nlp/N21_radio_intent.ipynb)
- [`notebooks/nlp/N22_ner_models.ipynb`](../../notebooks/nlp/N22_ner_models.ipynb)
- [`notebooks/nlp/N24_nlp_pipeline.ipynb`](../../notebooks/nlp/N24_nlp_pipeline.ipynb)
