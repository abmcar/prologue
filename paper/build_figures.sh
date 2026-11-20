#!/usr/bin/env bash
# Build every figure of the paper into paper/build/ with LuaLaTeX (TeX Live with pgfplots).
# usage: paper/build_figures.sh [name ...]      (default: all)
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p build
DATA="bg_split eval_pred eval_dist eval_blockreads eval_storage"
DIAG="binding plan overview prewarm_late"
for n in ${@:-$DATA $DIAG}; do
  if [ -e fig/${n}_standalone.tex ]; then
    lualatex -interaction=nonstopmode -halt-on-error -output-directory=build fig/${n}_standalone.tex > build/$n.out 2>&1 && mv build/${n}_standalone.pdf build/$n.pdf
  else
    lualatex -interaction=nonstopmode -halt-on-error -output-directory=build -jobname=$n "\def\figname{$n}\input{fig/schematic_standalone}" > build/$n.out 2>&1
  fi && echo "built build/$n.pdf" || { echo "FAILED $n (see build/$n.out)"; exit 1; }
done
