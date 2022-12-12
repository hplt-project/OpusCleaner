#!/usr/bin/env bash
set -euo pipefail
./placeholders.py --seed 1 -c static/config.yml -m mappings.yml --encode < static/test_encode_input > /tmp/test
./placeholders.py -m mappings.yml < /tmp/test --decode > /tmp/decoded
diff static/test_encode_input /tmp/decoded

# Test strict mode
./placeholders.py -c static/config.yml --encode --no-mapping --strict < static/test_encode_input_strict > /tmp/strict_diff
# Split lines and test First line should be the same
head -n1 static/test_encode_input_strict > /tmp/original_1
head -n1 /tmp/strict_diff > /tmp/strict_diff_1
diff /tmp/original_1 /tmp/strict_diff_1
# Second line should be different
tail -n1 static/test_encode_input_strict > /tmp/original_2
tail -n1 /tmp/strict_diff > /tmp/strict_diff_2
diff /tmp/original_2 /tmp/strict_diff_2
