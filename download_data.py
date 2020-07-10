import youtube_dl
from urllib.parse import urlparse, parse_qs
from vtt_to_srt.__main__ import vtt_to_srt
import os
import yaml
from tqdm import tqdm
from argparse import ArgumentParser
from utils import suppress_stdout

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--input', type=str)
    parser.add_argument('--retries', type=int, default=3)
    parser.add_argument('--lang', type=str, default='en,en-US,en-GB,en-CA,en-AU')
    parser.add_argument('--proxy', type=str, default=None)
    args = parser.parse_args()

    input_path = args.input
    num_tries = args.retries
    subtitles_langs = args.lang.split(',')
    proxy = args.proxy

    print('Downloading subtitles for languages:', subtitles_langs)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join('data', '%(id)s', 'clip.%(ext)s'),
        # 'postprocessors': [
        #     {
        #         'key': 'FFmpegExtractAudio',
        #         'preferredcodec': 'flac',
        #         'preferredquality': '0',
        #     },
        # ],
        'keepvideo': True,
        'writesubtitles': True,
        'extract_flat': True,
        # 'debug_printtraffic': True,
        'socket_timeout': 10,
        'quiet': True,
        'proxy': proxy,
    }

    with open(input_path) as f:
        inputs = yaml.safe_load(f)

    def log(obj):
        tqdm.write(str(obj))

    with youtube_dl.YoutubeDL(ydl_opts) as ydl, \
        tqdm(total=len(inputs), desc='total') as pbar, \
        tqdm(desc='playlist') as playlist_pbar:

        for input in inputs:
            try:
                input_url = input['url']
                parsed_url = urlparse(input_url)
                query_params = parse_qs(parsed_url.query)

                if 'v' in query_params:
                    ids = query_params['v']
                elif 'list' in query_params:
                    result = ydl.extract_info(input_url, download=False)

                    ids = [entry['id'] for entry in result['entries']]
                else:
                    log(f'Skipping invalid youtube URL: {input_url}')
                    continue

                playlist_pbar.total = len(ids)
                playlist_pbar.n = 1
                for id in ids:
                    try:
                        url = f'https://youtube.com/watch?v={id}'

                        if any([os.path.exists(os.path.join('data', id, f'clip.{subtitles_lang}.srt')) for subtitles_lang in subtitles_langs]):
                            pass
                            # log(f'SRT file for {id} exists. Skipping')
                        elif os.path.exists(os.path.join('data', id, '.no-subtitles')):
                            log(f'No subtitles exist for {id}. Skipping')
                        elif os.path.exists(os.path.join('data', id, '.inaccessible')):
                            log(f'Video {id} is not accessible. Skipping')
                        else:
                            # log(f'Retrieveing clip {id} from {url}')
                            try:
                                result = ydl.extract_info(url, download=False)
                            except (youtube_dl.utils.ExtractorError, youtube_dl.utils.DownloadError) as e:
                                log(f'Could not extract video information for {url}: {e}')

                                if 'This video is private.' in str(e):
                                    os.makedirs(os.path.join('data', id), exist_ok=True)
                                    with open(os.path.join('data', id, '.inaccessible'), 'w') as f:
                                        f.write(str(e))

                                continue

                            # Find first subtitle video has out of provided list
                            found_subtitles = next(filter(lambda available_lang: available_lang.lower() in [x.lower() for x in subtitles_langs], result['subtitles']), None)
                            if found_subtitles is not None:
                                entry_url = result['webpage_url']

                                for i in range(num_tries):
                                    try:
                                        ydl.params['subtitleslangs'] = [found_subtitles]
                                        ydl.download([entry_url])
                                        break
                                    except youtube_dl.utils.DownloadError as e:
                                        # log(f'Received download error: {e}')
                                        if i < num_tries:
                                            log(f'Retry #{i + 1}/{num_tries - 1}')
                                        else:
                                            log(f"Couldn't download video {id} ({entry_url}).")
                            else:
                                os.makedirs(os.path.join('data', id), exist_ok=True)
                                with open(os.path.join('data', id, '.no-subtitles'), 'w') as f:
                                    f.write('')

                                log(f'Could not find subtitles for {id}!')

                        for subtitles_lang in subtitles_langs:
                            vtt_path = os.path.join('data', id, f'clip.{subtitles_lang}.vtt')
                            if os.path.exists(vtt_path):
                                with suppress_stdout():
                                    vtt_to_srt(vtt_path)

                    finally:
                        playlist_pbar.update()
            finally:
                pbar.update()

log('Done')
