#!/usr/bin/env bash
# $1 = seed, $2 = outputfile, $3 = inputfile
shuf --random-source=<(openssl enc -aes-256-ctr -pass pass:"$1" -nosalt </dev/zero 2>/dev/null) -o $2 $3
