from glob import glob
import pysrt
from utils import filter_sub_text
from languages import LanguageEnglish, LanguageHebrew
from argparse import ArgumentParser
from tqdm import tqdm

parser = ArgumentParser()
parser.add_argument('--language', help='Language of expected subtitles. Used for cleaning the outputs.', type=str, default='en')
parser.add_argument('--output', help='Output path for corpus to be written in', type=str)
parser.add_argument('--input_dir', help='Input directory containing SRT files to collect', type=str)

args = parser.parse_args()

language_code = args.language
input_dir_path = args.input_dir
output_path = args.output


if language_code == 'en':
    language = LanguageEnglish()
elif language_code == 'iw':
    language = LanguageHebrew()
else:
    raise Exception(f'Unknown language {language_code}')


def transform(t):
    result = filter_sub_text(t, language)
    return result


srt_paths = tqdm(glob(f'{input_dir_path}/**/*.srt', recursive=True))
srt_subs = tqdm(pysrt.open(srt_path) for srt_path in srt_paths)
sub_texts = (sub.text for subs in srt_subs for sub in subs)

transformed_texts = (transform(t) for t in sub_texts)
filtered_texts = (t for t in transformed_texts if t is not None)
corpus_text = '\n'.join(filtered_texts)

with open(output_path, 'w') as f:
    f.write(corpus_text)

