# Placeholders script usage
Assumes the user uses `spm` vocabulary. Reads from `stdin` and writes to `stdout`. The encoder also writes a mapping file that contains all the spm mappings.
# Dump placeholders
Check what placeholders you want in your vocab:
```bash
./placeholders.py --dump_placeholders -c static/config.yml
```
Note that at this point `config.yml` shouldn't have a `vocab` entry.
# encode
```bash
./placeholders.py -c static/config.yml -m mappings.yml --encode < static/test_encode_input > /tmp/test
```
# decode
```bash
./placeholders.py -m mappings.yml --decode < /tmp/test > /tmp/decoded
```
# test
```bash
diff static/test_encode_input /tmp/decoded
```
# decode output and encode input should be the same
diff static/test_encode_input static/test_decode_output
```
