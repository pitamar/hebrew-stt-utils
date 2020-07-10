from argparse import ArgumentParser
from tqdm import tqdm
from languages import languages
from utils import filter_sub_text

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--input', type=str)
    parser.add_argument('--output', type=str)
    parser.add_argument('--limit', help='Limit number of files to process', type=int, default=None)
    parser.add_argument('--language', help='Language of expected subtitles. Used for cleaning the outputs.', choices=languages.keys(), default='en')
    args = parser.parse_args()

    limit = args.limit
    language_code = args.language
    input_path = args.input
    output_path = args.output

    language = languages[language_code]

    with open(input_path, 'r') as f:
        lines = f.read().split('\n')

    results = []
    for line in tqdm(lines[:limit]):
        result = filter_sub_text(line, language)
        results.append(result)

    with open(output_path, 'w') as f:
        for result in results:
            if result is not None:
                f.write(f'{result}\n')

