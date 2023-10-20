#!/bin/bash --login
set -e
conda activate hyp3-autorift
exec python -um hyp3_autorift "$@"
