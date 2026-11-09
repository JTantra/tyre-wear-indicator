# Shared contracts
Preprocessing, dataset audit/splits, train-only grouped head selection, costs and ledger/provider contracts live here.
head_selection.py preserves the declared grid, tie order, class weights, seeds and fold algorithms.
training.py executes exactly one fixed method, delegating actual encoding to that method's inference.py;
it does not mutate candidate globals or call historical run-all experiments.
results/ holds the frozen anonymous cross-method join and dataset partitions used to verify totals.
Each method owns its individual exact projection under results/. These are verified views, not recomputed API predictions.
No raw samples, feature matrices, customer images or private provider replies are published.
owned-heads.json binds only inspected final scaler/coefficients to the trusted original head hashes.
