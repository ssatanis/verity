#!/bin/bash
# Parallel ranged, resumable download of the 3 GB Medicaid provider spending parquet. Re-run until it prints COMPLETE.
cd "$(dirname "$0")/../data/medicaid_tmsis" || exit 1
U="https://stopendataprod.blob.core.windows.net/datasets/medicaid-provider-spending/2026-02-09/dataset/medicaid-provider-spending.parquet"
SZ=3072545478; N=12; CH=$((SZ/N+1)); mkdir -p parts
for i in $(seq 0 $((N-1))); do
  s=$((i*CH)); e=$((s+CH-1)); [ $e -ge $SZ ] && e=$((SZ-1)); f=parts/p$(printf %02d $i); have=0; [ -f $f ] && have=$(stat -c %s $f)
  if [ $have -lt $((e-s+1)) ]; then curl -sSL --retry 5 -r $((s+have))-$e -o - "$U" >> $f & fi
done; wait
tot=$(cat parts/p* | wc -c 2>/dev/null); tot=$(du -cb parts/p* | tail -1 | cut -f1)
echo "have $tot of $SZ"
if [ "$tot" -eq "$SZ" ]; then cat parts/p* > medicaid-provider-spending.parquet && echo "$U" > medicaid-provider-spending.parquet.done && rm -rf parts && echo COMPLETE; fi
