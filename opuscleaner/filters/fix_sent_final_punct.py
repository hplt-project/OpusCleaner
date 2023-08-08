#!/usr/bin/env python3
import sys

my_punct = ['!', '"', '#', '$', '%', '&', "'", '(', ')', '*', '+', ',', '.', '/', ':', ';', '<', '=', '>', '?', '@', '[', '\\', ']', '^', '_', '`', '{', '|', '}', '~', '»', '«', '“', '”']

for line in sys.stdin:
    src, trg = line.rstrip("\r\n").split("\t")
    # Sometimes we have a space between the final letter and the punctuation
    if src[-1] in my_punct and src[-2] == " ":
        src = src[:-2] + src[-1]
    if trg[-1] in my_punct and trg[-2] == " ":
        trg = trg[:-2] + trg[-1]
    # check for the french quotes special case
    if src[-1] == '»' or src[-1] == '«' and trg[-1] not in my_punct:
        trg = trg + '"'
    elif trg[-1] == '»' or trg[-1] == '«' and src[-1] not in my_punct:
        src = src + '"'
    elif src[-1] in my_punct and trg[-1] not in my_punct:
        trg = trg + src[-1]
    elif trg[-1] in my_punct and src[-1] not in my_punct:
        src = src + trg[-1]
    elif trg[-1] in my_punct and src[-1] in my_punct and src[-1] != trg[-1]:
        trg = trg[:-1] + src[-1]
    print(src + '\t' + trg)
