import re


class Language:
    @property
    def name(self):
        raise NotImplementedError()

    @property
    def blacklist(self):
        raise NotImplementedError()

    def filter_text(self, text):
        raise NotImplementedError()


class LanguageHebrew(Language):
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
        result = re.sub(r"[^אבגדהוזחטיכךלמםנןסעפףצץקרשת' \.,?0-9]", '', text)
        return result


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

