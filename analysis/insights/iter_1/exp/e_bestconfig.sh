#!/bin/bash
# Read-only: dump Inductor's runtime-autotuned reduction configs (*.best_config) from each live node's
# node-local compile cache (/tmp/cloq_<job>/torchinductor_ziyangs), for kernels whose reduction length equals a
# model's hidden size (q30a3 2048, q4 2560, q8 4096, q14/q32 5120). One TSV per node in ./out/.
# Columns: r0_numel  kernel_source_file  best_config_mtime  XBLOCK  R0_BLOCK  num_warps
# usage: bash e_bestconfig.sh node003:49604 node004:49603 node005:49596 node006:49597 node001:49605
cd "$(dirname "$0")"; mkdir -p out
for pair in "$@"; do
  n=${pair%:*}; j=${pair#*:}
  timeout 120 ssh -o BatchMode=yes "$n" "cd /tmp/cloq_$j/torchinductor_ziyangs 2>/dev/null || exit 0
    for R in 2048 2560 4096 5120; do
      for p in \$(grep -rl \"r0_numel = \$R\$\" --include=*.py .); do d=\$(dirname \$p)
        for b in \$d/*.best_config; do [ -f \$b ] || continue
          printf '%s\t%s\t%s\t%s\n' \$R \$(basename \$p) \"\$(stat -c %y \$b | cut -c1-19)\" \
            \"\$(python3 -c 'import json,sys;c=json.load(open(sys.argv[1]));print(c[\"XBLOCK\"],c.get(\"R0_BLOCK\"),c[\"num_warps\"],sep=chr(9))' \$b)\"
        done; done; done" | sort > "out/bestconfig_${n}_job${j}.tsv"
  echo "$n job $j: $(wc -l < out/bestconfig_${n}_job${j}.tsv) kernel configs"
done
