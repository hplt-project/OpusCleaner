#!/usr/bin/env python3
"""Common filtering code to be used by various submodules"""

CHARS = {
    'bg': r'[АаБбВвГгДддЕеЖжЗзИиЙйКкkasЛлМмНнОоПпРрСсТтУуФфХхЦцЧчШшЩщЪъЬьЮюЯя]',
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
    'is': r'[abdefghijklmnoprstuvxyÁáðÐÉéÍíÓóÚúÝýÞþÆæÖö]',
    'it': r'[a-zàÀèÈéÉìÌíÍîÎòÒóÓùÙúÚ]',
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
    'sv': r'[a-zÅåÄäÖö]',
}
