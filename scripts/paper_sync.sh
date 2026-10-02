#!/bin/bash
# Two-way sync between cloq/paper/latex (source of truth for numbers; check_numbers.py runs here) and the
# Overleaf-facing repo W4ng77/cloq-paper (private; Overleaf GitHub sync). Curated set only: no old drafts,
# no internal notes, no build artefacts.
#   scripts/paper_sync.sh push   # cloq -> cloq-paper (commit + push)
#   scripts/paper_sync.sh pull   # cloq-paper (e.g. Overleaf edits) -> cloq/paper/latex (then review, check_numbers, commit)
set -euo pipefail
SRC=/data/ziyangs/cloq/paper/latex
DST=/data/ziyangs/cloq-paper
[ -d $DST/.git ] || git clone -q https://github.com/W4ng77/cloq-paper.git $DST
FILES="main.tex acl.sty acl_natbib.bst refs.bib custom.bib"
DIRS="sections figures"
case "${1:-}" in
  push)
    git -C $DST pull -q --rebase || true
    for f in $FILES; do [ -f $SRC/$f ] && cp $SRC/$f $DST/; done
    for d in $DIRS; do [ -d $SRC/$d ] && rsync -a --delete --exclude old/ --exclude '*.aux' $SRC/$d/ $DST/$d/; done
    cp $SRC/main.pdf $DST/main_local_build.pdf 2>/dev/null || true
    git -C $DST add -A
    git -C $DST commit -qm "sync from cloq $(git -C /data/ziyangs/cloq rev-parse --short HEAD)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" && git -C $DST push -q || echo "nothing to sync"
    ;;
  pull)
    git -C $DST pull -q --rebase
    for f in $FILES; do [ -f $DST/$f ] && cp $DST/$f $SRC/; done
    for d in $DIRS; do [ -d $DST/$d ] && rsync -a --exclude old/ $DST/$d/ $SRC/$d/; done
    echo "pulled into $SRC; now: git -C /data/ziyangs/cloq diff -- paper/latex; python3 paper/latex/check_numbers.py"
    ;;
  *) echo "usage: $0 push|pull"; exit 2;;
esac
