#!/bin/bash --login
set -e
conda activate hyp3-autorift
exec python -u hyp3_autorift "$@"
