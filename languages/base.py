class Language:
    @property
    def name(self):
        raise NotImplementedError()

    @property
    def blacklist(self):
        raise NotImplementedError()

    def filter_text(self, text):
        raise NotImplementedError()
