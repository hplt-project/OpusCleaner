# Placeholders script usage
```
# encode
python3 placeholders.py -s static/test_encode_input -t static/test_encode_output --encode --vocab vocab.fren.spm --config config.yml
# decode
python3 placeholders.py -s static/test_encode_output -t static/test_decode_output --decode --vocab static/vocab.fren.spm --config static/config.yml
# decode output and encode input should be the same
diff static/test_encode_input static/test_decode_output
```
