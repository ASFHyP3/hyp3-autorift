#!/bin/bash --login
set -e
conda activate hyp3-autorift-radar
exec python -um hyp3_autorift "$@"
