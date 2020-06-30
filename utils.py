import re
from contextlib import contextmanager
import sys
import os
import pysrt
import codecs


@contextmanager
def suppress_stdout():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout


def srt_to_audacity_labels(srt_file_path, output_file_path):
    subs = pysrt.open(srt_file_path, encoding='utf-8')

    output = codecs.open(output_file_path, 'w', 'utf-8')

    for s in subs:
        start = s.start.hours * 60 * 60 + s.start.minutes * 60 + s.start.seconds + s.start.milliseconds / 1000.0
        end = s.end.hours * 60 * 60 + s.end.minutes * 60 + s.end.seconds + s.end.milliseconds / 1000.0
        output.write("%.6f\t%.6f\t%s\n" % (start, end, s.text.replace('\n', ' \\\\ ')))

    output.close()


def filter_sub_text(text, language):
    result = text

    # Reject strings with an english letter in it
    # match = re.search(r'[a-zA-Z]', str)
    # if match is not None:
    #     return None

    result = result.lower()
    result = re.sub(r'&[^&\;]{2,8}\;', '', result)  # Reemove HTML entities
    result = re.sub(r'\(' + r'[^\)]+' r'\)', '', result)  # Remove text in parenthesis
    result = re.sub(r'\[' + r'[^\]]+' r'\]', '', result)  # Remove text in brackets
    result = re.sub(r'\{' + r'[^\}]+' r'\}', '', result)  # Remove text in curly brackets
    result = re.sub(r'\<' + r'[^\>]+' r'\}', '', result)  # Remove text in triangular brackets
    result = re.sub(r'\s+', ' ', result)
    result = language.filter_text(result)
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()

    if result == '':
        return None

    return result

