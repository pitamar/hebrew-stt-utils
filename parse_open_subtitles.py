from glob import glob
from tqdm import tqdm
from multiprocessing import Pool
import xml.etree.ElementTree as ET
from argparse import ArgumentParser
import utils
from languages import languages
from utils import filter_sub_text
import re


def handler(xml_file, language):
    root = ET.parse(xml_file).getroot()
    s_tags = root.findall('s')

    sentences = []
    for s in s_tags:
        w_tags = s.findall('w')
        words = [w.text for w in w_tags]
        sentence = ' '.join(words)
        sentence = sentence.replace(" '", "'")

        if re.search('\d', sentence) is not None:
            sentences.append(None)
            continue

        filtered_sentence = sentence  # filter_sub_text(sentence, language)
        sentences.append(filtered_sentence)

    return sentences


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--workers', help='Number of processes to run concurrently', type=int, default=12)
    parser.add_argument('--limit', help='Limit number of files to process', type=int, default=None)
    parser.add_argument('--language', help='Language of expected subtitles. Used for cleaning the outputs.', choices=languages.keys(), default='en')
    parser.add_argument('--input_dir', type=str)
    parser.add_argument('--output', type=str)
    args = parser.parse_args()

    num_workers = args.workers
    language_code = args.language
    input_dir_path = args.input_dir
    output_path = args.output
    limit = args.limit

    language = languages[language_code]

    xml_files = glob(f'{input_dir_path}/**/*.xml', recursive=True)

    pbar = tqdm(total=len(xml_files))

    def update(*args):
        pbar.update()

    pool = Pool(num_workers)

    futures = []
    for xml_file in xml_files[:limit]:
        future = pool.apply_async(handler, args=(xml_file, language), callback=update)
        futures.append(future)

    pool.close()
    pool.join()

    results = []
    for future in futures:
        sentences = future.get()
        results.extend(sentences)

    with open(output_path, 'w') as f:
        for result in results:
            if result is not None:
                f.write(f'{result}\n')

