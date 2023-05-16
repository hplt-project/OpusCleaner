#!/usr/bin/env python3
import sys
import re
import argparse


mapping = [
	("\u0083", "É"),	# D<U+0083>CLARATION
	("\u0088", "à"),	# permettre <U+0088> lŐUnion
	("\u0089", "â"),	# probants obtenus gr<U+0089>ce aux
	("\u008d", "ç"),	# Recettes per<U+008D>ues
	("\u008e", "é"),	# d<U+008E>claration
	("\u008f", "è"),	# ci-apr<U+008F>s
	("\u0090", "ê"),	# doivent <U+0090>tre exclus
	("\u0091", "ë"),	# lŐexercice ont d<U+009E> être
	("\u0094", "î"),	# L'Agence reconna<U+0094>t
	("\u0099", "ô"),	# xLes contr<U+0099>les
	("\u009d", "ù"),	# dans la mesure o<U+009D> il
	("\u009e", "û"),	# l'exercice ont d<U+009E> être reportés
	("\u0092", "í"),    # V<U+0092>tor Manuel da SILVA CALDEIRA
	("Ő", "'"),         # lŐexercice
	("ă", "'"),         # ăAutoriteitÓ
	("Ó", "'"),
	("􏳕", "ë"),        # financi􏳕le
	("¬ ", ""),
]


class Translator:
	def __init__(self, mapping):
		self.mapping = {entry[0]: entry[1] for entry in mapping}
		self.pattern = re.compile('(' + '|'.join(self.mapping.keys()) + ')')
		self.callback = lambda match: self.mapping[match[0]]

	def __call__(self, input):
		return re.sub(self.pattern, self.callback, input)


def parse_user_args():
    parser = argparse.ArgumentParser(description="Fixes select encoding issues on the French side of the ELITR ECA dataset.")
    return parser.parse_args()


if __name__ == "__main__":
	args = parse_user_args()
	for line in sys.stdin:
		sys.stdout.write(Translator(mapping)(line))

