@echo off
echo === Step 1: Original images ===
bash scripts/run_original.sh

echo === Step 2: Robustness experiments ===
bash scripts/run_robustness.sh

echo === Done. Ket qua trong results/ ===