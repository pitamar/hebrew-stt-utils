import youtube_dl
from urllib.parse import urlparse, parse_qs
from vtt_to_srt.__main__ import vtt_to_srt
import os
import yaml
from argparse import ArgumentParser

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--retries', type=int, default=3)
    args = parser.parse_args()

    num_tries = args.retries
    subtitles_lang = 'iw'

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
        'subtitleslangs': [subtitles_lang],
        'extract_flat': True,
        # 'debug_printtraffic': True,
        'socket_timeout': 10,
    }

    with open('inputs.yaml') as f:
        inputs = yaml.safe_load(f)

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        for input in inputs:
            input_url = input['url']
            parsed_url = urlparse(input_url)
            query_params = parse_qs(parsed_url.query)

            if 'v' in query_params:
                ids = query_params['v']
            elif 'list' in query_params:
                result = ydl.extract_info(input_url, download=False)

                ids = [entry['id'] for entry in result['entries']]
            else:
                print('Skipping invalid youtube URL:', input_url)
                continue

            for id in ids:
                url = f'https://youtube.com/watch?v={id}'

                if os.path.exists(os.path.join('data', id, f'clip.{subtitles_lang}.srt')):
                    print(f'SRT file for {id} exists. Skipping')
                elif os.path.exists(os.path.join('data', id, '.no-subtitles')):
                    print(f'No subtitles exist for {id}. Skipping')
                else:
                    print(f'Retrieveing clip {id} from {url}')
                    try:
                        result = ydl.extract_info(url, download=False)
                    except (youtube_dl.utils.ExtractorError, youtube_dl.utils.DownloadError) as e:
                        print(f'Could not extract video information for {url}:', e)
                        continue

                    if subtitles_lang in result['subtitles']:
                        entry_url = result['webpage_url']

                        for i in range(num_tries):
                            try:
                                ydl.download([entry_url])
                                break
                            except youtube_dl.utils.DownloadError as e:
                                print('Received download error', e)
                                if i < num_tries:
                                    print(f'Retry #{i + 1}/{num_tries - 1}')
                                else:
                                    print(f"Couldn't download video {id} ({entry_url}).")
                    else:
                        os.makedirs(os.path.join('data', id), exist_ok=True)
                        with open(os.path.join('data', id, '.no-subtitles'), 'w') as f:
                            f.write('')

                        print(f'Could not find subtitles for {id}!')

                    vtt_path = os.path.join('data', id, f'clip.{subtitles_lang}.vtt')
                    if os.path.exists(vtt_path):
                        vtt_to_srt(vtt_path)

print('Done')
