#!/usr/bin/env bash
# Push the cleaned Humsana daemon (fresh clean history).
set -euo pipefail
REMOTE="git@github.com:sriramnatrajhen/humsana-daemon.git"   # or https://...
rm -rf .git __pycache__ */__pycache__ *.egg-info dist build *.log 2>/dev/null || true
if grep -rInE "humsana\.com/(pro|license)|humsana-auth-relay|hum_pro_[A-Za-z0-9]{6}" --include='*.py' . ; then
  echo "!! dead-link/secret reference found above - aborting."; exit 1
fi
echo "clean."
git init -q -b main
git add -A
git commit -q -m "Remove license gating and dead endpoints; fully open source, 100% local by default"
git remote add origin "$REMOTE"
git push -f origin main
echo "Done. (pip package: bump version in setup.py and re-publish to PyPI when ready.)"
