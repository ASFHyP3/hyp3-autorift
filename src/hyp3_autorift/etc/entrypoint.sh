#!/bin/bash --login
set -e
pixi run python -m hyp3_autorift "$@"
