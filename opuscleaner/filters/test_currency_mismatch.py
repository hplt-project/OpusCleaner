import io
import unittest
from typing import Optional

from currency_mismatch import filter_currency_mismatch

accept_examples = [
    # wrong numbers but correct currencies
    (
        'Base costs: Price: 25,410.00 € Price per 7 days Base costs: Base costs: 0.00 € More about the vessel »',
        'Kostenlos: Außenborder, Preis: 7.260,00 € Preis für 7 Tage Basiskosten: Basiskosten: 0,00 € Mehr über das Produkt »'
    ),

    # This is very rare and the regex captures only EUR near the number
    # £/$/€ -> €
    (
        'Players must make a minimum deposit of at least £/$/€ 100 to get a 50% up to £/$/€ 200 match bonus using code: 2017.',
        'Spieler müssen eine Einzahlung von mindestens 100 € machen, um einen Bonus von 50 % bis zu 200 € zu erhalten, wenn sie den Code: 2017 angeben.'
    ),

]

reject_examples = [

    # wrong number and currency
    (
        '1 of 16 B&Bs and Inns in Belfast From £75 per night.',
        'Nr. 1 von 16 Bed & Breakfasts und Gasthäusern in Belfast Ab € 85 pro Nacht.',
        'Nr. 1 von 16 Bed & Breakfasts und Gasthäusern in Belfast Ab £ 85 pro Nacht.'
    ),

    # $ -> EUR
    (
        'That’s $1200 a year that you could be saving.',
        'Das wären 1200 EUR, die du pro Jahr abzahlen kannst.',
        None
    ),

    # $ -> EUR
    (
        'RELATED: How to Add $5,000 to Your Savings By the End of the Year',
        'Wie Sie bis Ende des Jahres 5.000 EUR zu Ihren Ersparnissen hinzufügen können',
        None
    ),

    # $ -> Euro
    (
        'The cost to the city: $100,000.',
        'Die jährlichen Kosten für die Stadt: 100.000 Euro.',
        None
    ),

    # $ -> Euro
    (
        'The cost to the city: 100,000 USD.',
        'Die jährlichen Kosten für die Stadt: 100.000 EUR.',
        'Die jährlichen Kosten für die Stadt: 100.000 USD.'),

    # $ -> Euro
    (
        'So you get $500 in healthcare.',
        'Also bekommst du 500 Euro im Gesundheitswesen.',
        None),

    # $ -> €
    (
        'Assassin’s Creed Chronicles: India is the second installment of the series after Assassin’s Creed® Chronicles: China and is available for $9.99.',
        'Assassin’s Creed® Chronicles: India ist nach Assassin’s Creed® Chronicles: China die zweite Episode der Serie und für 9,99 € erhältlich.',
        'Assassin’s Creed® Chronicles: India ist nach Assassin’s Creed® Chronicles: China die zweite Episode der Serie und für 9,99 $ erhältlich.'),

    # $ -> CAD (Canadian dollar also uses $)
    (
        'These results represent a 280 percent increase in revenue over the previous fiscal year ($368,536) and a 286 percent increase of fourth quarter sales year over year, from $99,331 to $383,844.',
        'Diese Ergebnisse bedeuten eine Steigerung des Umsatzes um 280 % gegenüber dem Vorjahr (368.536 CAD) und eine Steigerung des Umsatzes im vierten Quartal um 286 % im Jahresvergleich von 99.331 CAD auf 383.844 CAD.',
        None
    ),

    # $ AUD -> AUD
    (
        'The Arthur scooter is designed to be economical and consumes just about $1 AUD per week with average daily usage.',
        'Der Roller ist sparsam konzipiert und verbraucht bei durchschnittlichem Tagesverbrauch nur etwa 1 AUD pro Woche.',
        None),

    # $ -> _ No currency
    (
        'Qualcomm Must Refund BlackBerry $815 Million in Fees',
        'Qualcomm soll Blackberry über 815 Millionen zahlen',
        None),

    # $ -> USD almost correct but it should be $ (very common!)
    (
        'Below this level, the next critical support is $66.1486.',
        'Unterhalb dieses Niveaus liegt die nächste Schlüsselunterstützung bei 66,1486 USD.',
        None
    ),

    # $ -> US-Dollar almost correct but it should be $ (very common!)
    (
        'College Students Can Now Get Sirius XM for $4 a Month',
        'College-Studenten können jetzt Sirius XM für 4 US-Dollar pro Monat erwerben',
        None
    ),

    # $ -> Dollar
    (
        'Look, according to expert analyses, Russia fell short by about $50 billion as a result of these restrictions during these years, starting in 2014.',
        'Schauen Sie, nach Angaben von Experten hat Russland als Folge all dieser Beschränkungen in den Jahren seit 2014 etwa 50 Milliarden Dollar verloren.',
        None
    ),

    # $ + USD -> USD
    (
        'If your own travel insurance does not include liability coverage up to $1,000,000 USD, we can offer this to you for an additional $12.25/day.',
        'Wenn Ihre Reiseversicherung keine Haftpflichtversicherung in Höhe von 1.000.000 USD umfasst, können wir Ihnen diese zusätzlich für 12,25 USD pro Tag anbieten.',
        None
    ),

    # £ -> Britischen Pfund
    (
        'Up to 64 teams will compete for a total prize pool of up to £5,000!',
        'Bis zu 64 Teams werden um einen Gesamtpreis in Höhe von bis zu 5.000 Britischen Pfund kämpfen!',
        None
    ),

    # £ -> €
    (
        'ABOUT US Get the scoop first and get £15 and a free pattern',
        'Erhalte als Erster alle Neuigkeiten, einen 15 €-Gutschein und eine kostenlose Anleitung',
        'Erhalte als Erster alle Neuigkeiten, einen 15 £-Gutschein und eine kostenlose Anleitung'
    ),

    # LTL -> лит, EURO -> EUR, LTL -> лита
    (
        'Prizes: Prize fund - 4000 LTL (1 EURO ~3.45 LTL)',
        'ПРИЗОВОЙ ФОНД - 4000 лит (1 EUR = 3,45 лита)',
        None
    )
]


class TestCurrencyMismatch(unittest.TestCase):
    def _test(self, line: str, **kwargs) -> Optional[str]:
        fin = io.StringIO(line)
        fout = io.StringIO()
        filter_currency_mismatch(fin, fout, **kwargs)
        return fout.getvalue()

    def assertAccept(self, line: str, **kwargs):
        """Test that this line is accepted"""
        self.assertTrue(self._test(line, **kwargs) == line)

    def assertReject(self, line: str, **kwargs):
        """Test that this line is rejected"""
        self.assertTrue(self._test(line, **kwargs) == "")

    def assertFixed(self, line: str, fixed_trg: str, **kwargs):
        """Test that this line was fixed"""
        output = self._test(line, **kwargs)
        src = line.split("\t")[0]
        fixed_line = f'{src}\t{fixed_trg}' if fixed_trg else ""
        self.assertTrue(output == fixed_line)

    def test_match(self):
        """Exact matches should be accepted."""
        self.assertAccept('Purchase options 5$ are great\tSomething else 5 $ hello', fix=False)

    def test_accept_no_number(self):
        """Exact matches should be accepted."""
        self.assertAccept('Purchase options $ are great\tSomething else EUR hello', fix=False)

    def test_mismatch(self):
        """Exact matches should be accepted."""
        self.assertReject('Purchase options 5$ are great\tSomething else 5 £ hello', fix=False)

    def test_fix(self):
        """Exact matches should be accepted."""
        self.assertFixed('Purchase options 5$ are great\tSomething else 5 £ hello',
                         'Something else 5 $ hello', fix=True)

    def test_different_iso_and_style(self):
        """Exact matches should be accepted."""
        self.assertReject('Purchase options 5$ are great\tSomething else 5 EUR hello',
                          fix=True)

    def test_symbol_code_mismatch(self):
        """Exact matches should be accepted."""
        self.assertReject('Purchase options 5$ are great\tSomething else 5 USD hello',
                          fix=True)

    def test_reject_examples_no_fix(self):
        for src, trg, _ in reject_examples:
            self.assertReject(f'{src}\t{trg}', fix=False)

    def test_accept_example(self):
        for src, trg in accept_examples:
            self.assertAccept(f'{src}\t{trg}', fix=True)

    def test_fix_examples(self):
        for src, trg, fixed in reject_examples:
            print(src)
            self.assertFixed(f'{src}\t{trg}', fixed, fix=True)
