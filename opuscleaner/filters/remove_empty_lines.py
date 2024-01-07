#!/usr/bin/env python3
import sys

def main():
    for line in sys.stdin:
        fields = line.strip("\r\n").split("\t")
        ok = True
        for field in fields:
            if not field.strip():
                ok = False
                break
        if ok:
            sys.stdout.write(line)

if __name__ == '__main__':
    main()
