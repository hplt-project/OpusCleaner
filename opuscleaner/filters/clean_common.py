#!/usr/bin/env python3
"""Common filtering code to be used by various submodules"""

CHARS = {
    'ar': r'[\u0600-\u06FF]', # This is not entirely right, as it also includes farsi symbols and whatnot
    'bg': r'[АаБбВвГгДддЕеЖжЗзИиЙйКкkasЛлМмНнОоПпРрСсТтУуФфХхЦцЧчШшЩщЪъЬьЮюЯя]',
    # Bosnian uses Latin script, but excludes [ywxq]
    #   Common diacritics: [čćđšžž]
    'bs': r'[abcdefghijklmnoprstuvzčćđšžž]',
    'bn': r'[\u0980-\u09FF]', # bangla
    'ca': r'[a-zÀàÈèÉéÍíÒòÓóÚúÇç]',
    'cs': r'[a-zÁáČčĎďÉéěÍíŇňÓóŘřŠšŤťÚúůÝýŽž]',
    'da': r'[a-zÆæØøÅå]',
    'de': r'[a-zÄäÖöÜüß]',
    'en': r'[a-z]',
    'el': r'[a-zΑαΒβΓγΔδΕεΖζΗηΘθΙιΚκΛλΜμΝνΞξΟοΠπΡρΣσςΤτΥυΦφΧχΨψΩω]',
    'es': r'[a-zÁáÉéÍíÓóÚúñÑ]',
    'et': r'[a-zÕõÄäÖöÜü]',
    'eu': r'[a-zñÑ]',
    'fi': r'[a-zÅåÄäÖö]',
    'fr': r'[a-zÂâÁáÀàâÇçÉéÈèÊêÓóÒòÔôŒœÜüÛûŸÿ]',
    'ga': r'[abcdefghilmnoprstuáéíóúÁÉÍÓÚ]',
    'gl': r'[a-zÁáÉéÍíÓóÚúÑñ]',
    'hi': r'[\u0900-\u097F]', # devanagari
    'hr': r'[abcčČćĆdđĐefghijklmnoprsšŠtuvzžŽ]',
    'hu': r'[a-zÁáÉéÍíÓóÖöŐőŰű]',
    'hy': r'[\u0530-\u058F]',
    # Indonesian uses the Latin script, without diacritics.
    'id': r'[a-z]',
    'is': r'[abdefghijklmnoprstuvxyÁáðÐÉéÍíÓóÚúÝýÞþÆæÖö]',
    'it': r'[a-zàÀèÈéÉìÌíÍîÎòÒóÓùÙúÚ]',
    # http://www.rikai.com/library/kanjitables/kanji_codes.unicode.shtml
    # Hiragana: \u3040-\u309F (Hiragana characters)
    # Katakana: \u30A0-\u30FF (Katakana characters)
    # Full-width roman characters and half-width katakana ( \uFF00-\uFFEF)
    # Kanji: \u4E00-\u9FAF (CJK unifed ideographs - Common and uncommon kanji)
    # Japanese Punctuation and Symbols: \u3000-\u303F (CJK Symbols and Punctuation, including ideographic spaces, quotation marks, iteration marks, etc.)
    # CJK unified ideographs Extension A - Rare kanji ( \u3400-\u4DBF )
    'ja': r'[\u3040-\u309F\u30A0-\u30FF\uFF00-\uFFEF\u4E00-\u9FAF\u3000-\u303F\u3400-\u4DBF]',
    'ko': r'[\uac00-\ud7af]|[\u1100-\u11ff]|[\u3130-\u318f]|[\ua960-\ua97f]|[\ud7b0-\ud7ff]',
    'lt': r'[aąbcČčdeĘęĖėfghiĮįyjklmnoprsŠštuŲųŪūvzŽž]',
    'lv': r'[aĀābcČčdeĒēfgĢģhiĪījkĶķlĻļmnŅņoprsŠštuŪūvzŽž]',
    'mt': r'[abĊċdefĠġghĦħiiejklmnopqrstuvwxŻżz]',
    'nb': r'[a-zÂâÁáÀàâÉéÈèÊêÓóÒòÔôÜüÆæØøÅå]',
    'nl': r'[a-zÂâÁáÀàâÉéÈèÊêÓóÒòÔôÚú]',
    'no': r'[a-zÂâÁáÀàâÉéÈèÊêÓóÒòÔôÜüÆæØøÅå]',
    'nn': r'[a-zÂâÁáÀàâÉéÈèÊêÓóÒòÔôÜüÆæØøÅå]',
    'pl': r'[a-zĄąĆćĘęŁłŃńÓóŚśŹźŻż]',
    'pt': r'[a-zÂâÁáÀàÃãÇçÉéÈèÊêÍíÌìÓóÒòÔôÕõÚúÙù]',
    'ro': r'[a-zĂăÂâÎîȘșȚț]',
    'ru': r'[а-я]',
    'sk': r'[a-záäÁÄčČďĎžéÉíÍĺĹľĽňŇóÓôÔŕŔšŠťŤúÚýÝžŽ]',
    'sl': r'[abcčČdđĐefghijklmnoprsšŠtuvzžŽ]',
    # Serbian is digraphic, and uses both Latin and Cyrillic
    #   Cyrillic outside of а-я: [јћњљђ]
    #   Latin extended: [ščćžđ]
    'sr': r'[a-zа-яјћњљђščćžđ]',
    'sv': r'[a-zÅåÄäÖö]',
    # Turkish is primarily Latin, with addition of the dotless i (ı) and other commonly
    # used diacritics:
    #   Latin Extended-A: [ışğ]
    #   Latin-1 Supplement: [üçöâîûÿ]
    #   U+0307 - Combining Dot Above ◌̇
    'tr': r'[a-zışğüçöâîûÿ\u0307]',
    'uk': r'[А-ЩЬЮЯҐЄІЇа-щьюяґєії\'`’ʼ]',
    'zh': r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]',
    # Vietnamese uses the Latin script [a-z]
    #   Sampled diacritics from HPLT data: 'àảãáạăằẳẵắặâầẩẫấậðđèẻẽéẹêềểễếệìỉĩíịòỏõóọôồổỗốộơờởỡớợùủũúụưừửữứựỳỷỹýỵ'
    'vi': r'[a-zàảãáạăằẳẵắặâầẩẫấậðđèẻẽéẹêềểễếệìỉĩíịòỏõóọôồổỗốộơờởỡớợùủũúụưừửữứựỳỷỹýỵ]',
}
