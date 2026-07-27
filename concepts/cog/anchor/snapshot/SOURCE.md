# Epoch AI snapshot provenance

- Source page: https://epoch.ai/data-insights/llm-inference-price-trends
- Source repository: https://github.com/epoch-research/llm-benchmark-efficiency
- Source file: `results/default/lowest_price_models_above_previous_frontier/lowest_price_models_data.csv`
- Commit: `34b923314338360d1b1bbed6ec30d9299e54fdae`
- Fetch date: 2026-07-27
- Vendored selection: the five `bench=MMLU`,
  `threshold_model=GPT-4-0314` rows (the source dataset's GPT-4 threshold).

Epoch's data page states:

> Epoch's work is free to use, distribute, and reproduce provided the source
> and authors are credited under the Creative Commons BY license.

The code repository did not contain a `LICENSE` file at the commit above.
CC-BY is asserted on Epoch AI's data pages; this snapshot records that statement
and its source rather than inferring a code-repository license.

Epoch documents the published USD-per-million-token series as a 3:1 weighted
average of input and output prices. COG-1 uses 4:1. The component prices are not
present in this CSV, so `normalize_blend()` marks the conversion `exact:false`
and emits an uncertainty interval.
