from .en import LanguageEnglish
from .iw import LanguageHebrew


languages = {lang.name: lang for lang in [LanguageEnglish(), LanguageHebrew()]}
