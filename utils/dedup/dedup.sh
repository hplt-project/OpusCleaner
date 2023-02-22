#!/usr/bin/env bash
# $1 old documents source
# $2 new documents target

# Delete old hashes
rm *.pickle

# Create the matching directory structure in the target location
dirs=`find $1 -type d | sed "s#${1}##g"`

for dir in $dirs; do
    mkdir -p ${2}/${dir}
done

# Create a list of files to be deduplicated
files=`find $1 -type f`

# Run the deduplicator on each one of them. In the process aggregate the hashes of seen files so that we
# Do not output the same sentence if it has been seen in a previous version of the dataset.
for file in $files; do
    myfileout=`sed "s#${1}##g" <<< "${file}"`
    echo "Deduplicating ${myfileout} ..."
    cat ${file} | ./hash-seg.py -a | ./superdedup.py | cut -f 1,2 > ${2}/${myfileout}
done
