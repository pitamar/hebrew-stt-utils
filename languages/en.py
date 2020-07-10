from .base import Language
import re


class LanguageEnglish(Language):
    @property
    def name(self):
        return 'en'

    @property
    def blacklist(self):
        return []

    def filter_text(self, text):
        # result = re.sub(r"[^a-zA-Z' \.,?0-9]", '', text)
        result = re.sub(r"[^a-zA-Z' 0-9]", '', text)
        return result
