# Deduplicator
Once we have finished preprocessing all the corpora with our filters we are left with many different files that might contain duplicates. To use the deduplicator you do:
`./dedup.sh ROOT_DIRECTORY_TO_CLEAN_FILES NEW_DIRECTORY_WHERE_ALL_DEDUPPED_FILES_WILL_BE_PLACED`

`dedup.sh` will take care of creating the same directory structure at the target location. The deduplicator also incrementally dumps `shashes.pickle` and `thashes.pickle` so that it keeps track of what lines it has seen so far across different files. The script will delete those files before it runs in order to make sure that you don't run into issues when moving to new datasets.

Based on the work of @ZJaume , the deduplicator also takes care of near duplicates that differ only by lower and upper case.
