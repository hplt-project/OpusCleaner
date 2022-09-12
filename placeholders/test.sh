#!/usr/bin/env bash
./placeholders.py -c static/config.yml -m mappings.yml --encode < static/test_encode_input > /tmp/test
./placeholders.py -m mappings.yml < /tmp/test --decode > /tmp/decoded
diff static/test_encode_input /tmp/decoded
