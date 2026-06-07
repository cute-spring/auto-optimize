# FAQ Retrieval Reference Example

This is a reference declaration and local regression fixture. It is not the required shape for user projects.

This example now does two jobs:

1. provides a minimal fixture for contract validation
2. provides realistic multilingual retrieval examples for future optimization runs

## Included Typical Cases

- Chinese user query -> Chinese FAQ
- English user query -> English FAQ
- Chinese user query -> bilingual FAQ title/body
- FAQ embedding template comparison
- user query embedding / query rewriting comparison

## Typical Embedding Dimensions

The example contract includes representative search-space dimensions for:

- `faq_embedding_template`
  - `question_only`
  - `question_with_answer`
  - `question_title_answer_bilingual`
- `query_embedding_template`
  - `raw_query`
  - `normalized_query`
  - `bilingual_expansion`
- `multilingual_normalization`
  - `true`
  - `false`

These are meant to model common production questions such as:

- Should FAQ embeddings include only the canonical question, or also title / answer / condition text?
- Should user queries be embedded as-is, normalized, or expanded into bilingual retrieval prompts?
- Does mixed Chinese-English support improve recall for bilingual help-center content?

## Data Files

- `workspace/data/golden_set.json`: multilingual retrieval evaluation set
- `workspace/data/embedding_cases.json`: focused embedding experiment matrix
- `workspace/configs/embedding_strategy.yaml`: example embedding knobs that the contract can optimize

## Run

```bash
python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml
```
