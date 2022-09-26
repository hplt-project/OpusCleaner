#!/usr/bin/env bash
set -euo pipefail
./placeholders.py --seed 1 -c static/config.yml -m mappings.yml --encode < static/test_encode_input > /tmp/test
./placeholders.py -m mappings.yml < /tmp/test --decode > /tmp/decoded
diff static/test_encode_input /tmp/decoded
