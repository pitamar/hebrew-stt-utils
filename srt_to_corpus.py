from glob import glob
import pysrt
from utils import filter_sub_text
from languages import languages
from argparse import ArgumentParser
from tqdm import tqdm


def transform(t):
    result = filter_sub_text(t, language)
    return result


def load_srt(file_path):
    subs = pysrt.open(file_path)
    texts = [sub.text for sub in subs]
    return texts


def load_txt(file_path):
    with open(file_path) as f:
        texts = f.readlines()
        return texts


if __name__ == '__main__':
    file_loaders = {
        'srt': load_srt,
        'txt': load_txt,
    }


    parser = ArgumentParser()
    parser.add_argument('--language', help='Language of expected subtitles. Used for cleaning the outputs.', choices=languages.keys(), default='en')
    parser.add_argument('--output', help='Output path for corpus to be written in', type=str)
    parser.add_argument('--input_dir', help='Input directory containing SRT files to collect', type=str)
    parser.add_argument('--input_type', help='Either SRT files or text files', choices=file_loaders.keys())
    args = parser.parse_args()


    language_code = args.language
    input_dir_path = args.input_dir
    output_path = args.output
    input_type = args.input_type


    file_paths = tqdm(glob(f'{input_dir_path}/**/*.{input_type}', recursive=True))

    file_loader = file_loaders[input_type]
    text_lists = (file_loader(file_path) for file_path in file_paths)
    all_texts = (text for texts in text_lists for text in texts)

    transformed_texts = (transform(t) for t in all_texts)
    filtered_texts = (t for t in transformed_texts if t is not None)

    with open(output_path, 'w') as f:
        for text in filtered_texts:
            f.write(f'{text}\n')

