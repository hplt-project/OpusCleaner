# Placeholders script usage
```
# encode
python3 placeholders.py -s static/placeholder-stuff/test_encode_input -t static/placeholder-stuff/test_encode_output --encode --vocab static/placeholder-stuff/vocab.fren.spm --config static/placeholder-stuff/config.yml
# decode
python3 placeholders.py -s static/placeholder-stuff/test_encode_output -t static/placeholder-stuff/test_decode_output --decode --vocab static/placeholder-stuff/vocab.fren.spm --config static/placeholder-stuff/config.yml
# decode output and encode input should be the same
diff static/placeholder-stuff/test_encode_input static/placeholder-stuff/test_decode_output
```
