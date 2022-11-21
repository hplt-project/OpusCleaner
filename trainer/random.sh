#!/usr/bin/env bash
# $1 = seed, $2 = outputfile, $3 = inputfile(s)
SEED="$1"
shift

OUTFILE="$1"
shift

cat "$@" | shuf --random-source=<(openssl enc -aes-256-ctr -pass pass:"$SEED" -nosalt </dev/zero 2>/dev/null) -o "$OUTFILE"
