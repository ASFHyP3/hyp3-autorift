#!/bin/bash --login
set -e
conda activate hyp3-autorift
exec hyp3_autorift "$@"
