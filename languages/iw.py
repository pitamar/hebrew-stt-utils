from typing import List, Union

from .base import Language
import re
import unittest
import math


class LanguageHebrew(Language):
    def __init__(self):
        self.number_transformer = NumberTransformer()

    @property
    def name(self):
        return 'iw'

    @property
    def blacklist(self):
        return [
            'כתוביות:',
            'תכתוב:',
            'לשידור:',
        ]

    def filter_text(self, text):
        result = text
        numeric_chars = r'\.?0-9\\\/\-'
        alphabet = 'אבגדהוזחטיכךלמםנןסעפףצץקרשת'
        result = re.sub(rf"[^{numeric_chars},' {alphabet}]", '', result)
        result = self.number_transformer.transform_text(result)
        result = re.sub(rf'[{numeric_chars}]', '', result)
        trans = str.maketrans(
            'ךםןףץ',
            'כמנפצ',
        )
        result = result.translate(trans)
        return result


class NumberTransformer:
    class Part:
        def __init__(self, value: int = None, label: str = '', decimal: bool = False):
            self.value = value
            self.label = label
            self.decimal = decimal

        def __repr__(self):
            return f'Part(value={self.value}, label="{self.label}", decimal={"True" if self.decimal else "False"})'


    zero_label = 'אפס'
    decimal_point_label = 'נקודה'
    decimal_labels = {
        5: 'חצי',
        25: 'רבע',
        75: 'שלושה רבעים',
    }
    thousand_count_labels = {
        3: 'שלושת',
        4: 'ארבעת',
        5: 'חמשת',
        6: 'ששת',
        7: 'שבעת',
        8: 'שמונת',
        9: 'תשעת',
    }
    labels = {
        2: 'שתיים',
        3: 'שלוש',
        4: 'ארבע',
        5: 'חמש',
        6: 'שש',
        7: 'שבע',
        8: 'שמונה',
        9: 'תשע',
        11: 'אחת עשרה',
        12: 'שתיים עשרה',
        13: 'שלוש עשרה',
        14: 'ארבע עשרה',
        15: 'חמש עשרה',
        16: 'שש עשרה',
        17: 'שבע עשרה',
        18: 'שמונה עשרה',
        19: 'תשע עשרה',
        20: 'עשרים',
        30: 'שלושים',
        40: 'ארבעים',
        50: 'חמישים',
        60: 'שישים',
        70: 'שבעים',
        80: 'שמונים',
        90: 'תשעים',
        200: 'מאתיים',
        2000: 'אלפיים',
        3000: 'שלושת אלפים',
        4000: 'ארבעת אלפים',
        5000: 'חמשת אלפים',
        6000: 'ששת אלפים',
        7000: 'שבעת אלפים',
        8000: 'שמונת אלפים',
        9000: 'תשעת אלפים',
        10000: 'עשרת אלפים',
    }
    units = {
        0: {'get_unit_label': lambda x: 'אחת'},
        1: {'get_unit_label': lambda x: 'עשר'},
        2: {'get_unit_label': lambda x: 'מאה' if x == 1 else 'מאות'},
        3: {
            'get_unit_label': lambda x: 'אלף' if x == 1 or x >= 10 else 'אלפים',
            'get_count_label': lambda x: NumberTransformer.thousand_count_labels.get(x),
        },
        6: {'get_unit_label': lambda x: 'מליון'},
        9: {'get_unit_label': lambda x: 'מליארד'},
    }

    symbol_labels = {
        '%': lambda x: 'אחוז',
        '$': lambda x: 'דולר',
        '€': lambda x: 'יורו',
        '₪': lambda x: 'שקל' if x == 1 else 'שקלים',
        '°': lambda x: 'מעלה' if x == 1 else 'מעלות',
    }
    symbols_regexp = rf'[{"".join(symbol_labels.keys())}]'
    number_regexp = rf'({symbols_regexp})?(\d[\d,]*(?:\.\d+)?)({symbols_regexp})?'

    def transform_text(self, text):
        replaced_text = re.sub(
            self.number_regexp,
            lambda match: self.transform_number(match.group(2), symbol=match.group(1) or match.group(3)),
            text,
        )
        return replaced_text

    def transform_number(self, value, symbol=None):
        if type(value) == str:
            numeric_str = re.sub(r'[^\d\.]', '', value)
            whole, decimal = ([int(x) for x in numeric_str.split('.')] + [None])[:2]
            number = float(numeric_str)
        elif type(value) == int:
            whole, decimal = value, None
            number = whole

        parts = self.parse_whole_number(whole)
        parts = self.parse_decimal_part(decimal, whole_parts=parts)
        part_labels = [part.label for part in parts]

        if symbol is not None:
            symbol_label = self.symbol_labels[symbol](number)
            part_labels.append(symbol_label)

        result = ' '.join(part_labels)

        return result

    def parse_decimal_part(self, decimal_value: int, whole_parts: List[Part]) -> List[Part]:
        if decimal_value is None:
            return whole_parts

        if decimal_value in self.decimal_labels:
            label = self.decimal_labels[decimal_value]
            part = NumberTransformer.Part(value=decimal_value, label=label)

            if len(whole_parts) == 1 and whole_parts[0].value == 0:
                return [part]

            part.label = f'ו{part.label}'
            return whole_parts + [part]

        decimal_point_part = NumberTransformer.Part(label=self.decimal_point_label)

        if decimal_value < 1000:
            decimal_parts = self.parse_whole_number(decimal_value)
            result = whole_parts + [decimal_point_part] + decimal_parts
            return result

        decimal_parts = []
        while decimal_value > 0:
            digit = decimal_value % 10
            digit_part = self.parse_whole_number(digit)[0]
            decimal_parts.insert(0, digit_part)

            decimal_value //= 10

        if len(decimal_parts) > 0:
            decimal_parts.insert(0, decimal_point_part)

        result = whole_parts + decimal_parts
        return result

    def parse_whole_number(self, value: int) -> List[Part]:
        if value in self.labels:
            label = self.labels[value]
            result = [NumberTransformer.Part(value=value, label=label)]
            return result

        if value == 0:
            result = [NumberTransformer.Part(value=value, label=self.zero_label)]
            return result

        for next_power, next_unit_dict in self.units.items():
            next_unit_value = 10 ** next_power
            if next_unit_value > value:
                break
            power, unit_dict = next_power, next_unit_dict
            unit_value = next_unit_value

        if value % unit_value == 0:
            unit_count = value // unit_value
            unit_label = unit_dict['get_unit_label'](unit_count)
            label_parts = [unit_label]

            if unit_count > 1:
                unit_count_labels = [None]
                if 'get_count_label' in unit_dict:
                    unit_count_labels = [unit_dict['get_count_label'](unit_count)]

                if unit_count_labels == [None]:
                    unit_count_parts = self.parse_whole_number(unit_count)
                    unit_count_labels = [part.label for part in unit_count_parts]

                label_parts = unit_count_labels + label_parts

            label = ' '.join(label_parts)
            result = [NumberTransformer.Part(value=value, label=label)]

            return result

        parts = []
        unit_count = (value // unit_value) * unit_value
        unit_count_parts = self.parse_whole_number(unit_count)

        parts += unit_count_parts

        remainder = value % unit_value
        remainder_parts = self.parse_whole_number(remainder)

        last_part = remainder_parts[0]
        if remainder < 20:
            last_part.label = f'ו{last_part.label}'

        parts += remainder_parts

        return parts


class NumberTransformerTest(unittest.TestCase):
    def setUp(self):
        self.number_transformer = NumberTransformer()

    def test_zero(self):
        self.assertEqual(self.number_transformer.transform_number('0'), 'אפס')

    def test_single_digit_number(self):
        self.assertEqual(self.number_transformer.transform_number('3'), 'שלוש')
        self.assertEqual(self.number_transformer.transform_number('4'), 'ארבע')
        self.assertEqual(self.number_transformer.transform_number('5'), 'חמש')
        self.assertEqual(self.number_transformer.transform_number('6'), 'שש')
        self.assertEqual(self.number_transformer.transform_number('7'), 'שבע')
        self.assertEqual(self.number_transformer.transform_number('8'), 'שמונה')
        self.assertEqual(self.number_transformer.transform_number('9'), 'תשע')

    def test_teen_numbers(self):
        self.assertEqual(self.number_transformer.transform_number('11'), 'אחת עשרה')
        self.assertEqual(self.number_transformer.transform_number('12'), 'שתיים עשרה')
        self.assertEqual(self.number_transformer.transform_number('16'), 'שש עשרה')
        self.assertEqual(self.number_transformer.transform_number('19'), 'תשע עשרה')

    def test_whole_two_digit_numbers(self):
        self.assertEqual(self.number_transformer.transform_number('20'), 'עשרים')
        self.assertEqual(self.number_transformer.transform_number('30'), 'שלושים')
        self.assertEqual(self.number_transformer.transform_number('60'), 'שישים')
        self.assertEqual(self.number_transformer.transform_number('90'), 'תשעים')

    def test_whole_units(self):
        self.assertEqual(self.number_transformer.transform_number('1'), 'אחת')
        self.assertEqual(self.number_transformer.transform_number('10'), 'עשר')
        self.assertEqual(self.number_transformer.transform_number('100'), 'מאה')
        self.assertEqual(self.number_transformer.transform_number('1000'), 'אלף')
        self.assertEqual(self.number_transformer.transform_number('1000000'), 'מליון')
        self.assertEqual(self.number_transformer.transform_number('1000000000'), 'מליארד')

    def test_double_units(self):
        self.assertEqual(self.number_transformer.transform_number('2'), 'שתיים')
        self.assertEqual(self.number_transformer.transform_number('20'), 'עשרים')
        self.assertEqual(self.number_transformer.transform_number('200'), 'מאתיים')
        self.assertEqual(self.number_transformer.transform_number('2000'), 'אלפיים')

    def test_complex_two_digit_numbers(self):
        self.assertEqual(self.number_transformer.transform_number('23'), 'עשרים ושלוש')
        self.assertEqual(self.number_transformer.transform_number('55'), 'חמישים וחמש')
        self.assertEqual(self.number_transformer.transform_number('91'), 'תשעים ואחת')

    def test_complex_three_digit_numbers(self):
        self.assertEqual(self.number_transformer.transform_number('301'), 'שלוש מאות ואחת')
        self.assertEqual(self.number_transformer.transform_number('250'), 'מאתיים חמישים')
        self.assertEqual(self.number_transformer.transform_number('999'), 'תשע מאות תשעים ותשע')
        self.assertEqual(self.number_transformer.transform_number('712'), 'שבע מאות ושתיים עשרה')
        self.assertEqual(self.number_transformer.transform_number('610'), 'שש מאות ועשר')

    def test_complex_four_digit_numbers(self):
        self.assertEqual(self.number_transformer.transform_number('4005'), 'ארבעת אלפים וחמש')
        self.assertEqual(self.number_transformer.transform_number('6100'), 'ששת אלפים מאה')
        self.assertEqual(self.number_transformer.transform_number('8015'), 'שמונת אלפים וחמש עשרה')
        self.assertEqual(self.number_transformer.transform_number('9999'), 'תשעת אלפים תשע מאות תשעים ותשע')

    def test_complex_long_digit_numbers(self):
        self.assertEqual(self.number_transformer.transform_number('16000000'), 'שש עשרה מליון')
        self.assertEqual(self.number_transformer.transform_number('22100001'), 'עשרים ושתיים מליון מאה אלף ואחת')
        self.assertEqual(self.number_transformer.transform_number('96000000015'), 'תשעים ושש מליארד וחמש עשרה')

    def test_plural_units(self):
        self.assertEqual(self.number_transformer.transform_number('300'), 'שלוש מאות')
        self.assertEqual(self.number_transformer.transform_number('500'), 'חמש מאות')
        self.assertEqual(self.number_transformer.transform_number('4000'), 'ארבעת אלפים')
        self.assertEqual(self.number_transformer.transform_number('10000'), 'עשרת אלפים')
        self.assertEqual(self.number_transformer.transform_number('20000'), 'עשרים אלף')
        self.assertEqual(self.number_transformer.transform_number('200000'), 'מאתיים אלף')
        self.assertEqual(self.number_transformer.transform_number('6000000'), 'שש מליון')
        self.assertEqual(self.number_transformer.transform_number('7000000000'), 'שבע מליארד')
        self.assertEqual(self.number_transformer.transform_number('100000000000'), 'מאה מליארד')
        self.assertEqual(self.number_transformer.transform_number('500000000000'), 'חמש מאות מליארד')

    def test_simple_decimals(self):
        self.assertEqual(self.number_transformer.transform_number('0.5'), 'חצי')
        self.assertEqual(self.number_transformer.transform_number('5.5'), 'חמש וחצי')
        self.assertEqual(self.number_transformer.transform_number('23.25'), 'עשרים ושלוש ורבע')
        self.assertEqual(self.number_transformer.transform_number('100.75'), 'מאה ושלושה רבעים')

    def test_complex_decimals(self):
        self.assertEqual(self.number_transformer.transform_number('0.12345'), 'אפס נקודה אחת שתיים שלוש ארבע חמש')
        self.assertEqual(self.number_transformer.transform_number('101.999'), 'מאה ואחת נקודה תשע מאות תשעים ותשע')
        self.assertEqual(self.number_transformer.transform_number('20.55'), 'עשרים נקודה חמישים וחמש')

    def test_transform_text(self):
        self.assertEqual(
            self.number_transformer.transform_text(
                'הלכתי לקנות 21 עוגיות'
            ),
            'הלכתי לקנות עשרים ואחת עוגיות'
        )

        self.assertEqual(
            self.number_transformer.transform_text(
                'המוצר הזה עולה 1,250.5 שקלים פלוס 17 אחוז מע"מ'
            ),
            'המוצר הזה עולה אלף מאתיים חמישים וחצי שקלים פלוס שבע עשרה אחוז מע"מ'
        )
        
        self.assertEqual(
            self.number_transformer.transform_text(
                'המוצר הזה עולה 1,250.5₪ פלוס 17% מע"מ'
            ),
            'המוצר הזה עולה אלף מאתיים חמישים וחצי שקלים פלוס שבע עשרה אחוז מע"מ'
        )
