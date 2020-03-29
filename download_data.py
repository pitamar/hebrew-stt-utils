import youtube_dl
from urllib.parse import urlparse, parse_qs
from vtt_to_srt.__main__ import vtt_to_srt
import os

if __name__ == '__main__':
    subtitles_lang = 'iw'

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'data/%(id)s/clip.%(ext)s',
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '0',
            },
        ],
        'keepvideo': True,
        'writesubtitles': True,
        'subtitleslangs': [subtitles_lang],
        'extract_flat': True,
        # 'debug_printtraffic': True,
        'socket_timeout': 10,
    }

    with open('./batch.txt') as f:
        lines = f.read().splitlines()
        urls = [url.strip() for url in lines if url.strip() != '' and not url.startswith('#')]

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        for url in urls:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)

            if 'list' in query_params:
                result = ydl.extract_info(url, download=False)

                ids = [entry['id'] for entry in result['entries']]
            else:
                ids = query_params['v']

            for id in ids:
                url = f'https://youtube.com/watch?v={id}'

                if os.path.exists(f'data/{id}/clip.wav'):
                    print(f'WAV file for {id} exists. Skipping')
                else:
                    print(f'Retrieveing clip {id} from {url}')
                    result = ydl.extract_info(url, download=False)

                    if subtitles_lang in result['subtitles']:
                        entry_url = result['webpage_url']

                        num_tries = 3
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
                        print(f'No subtitles exist for {id}!')

                vtt_path = f'data/{id}/clip.{subtitles_lang}.vtt'
                if os.path.exists(vtt_path):
                    vtt_to_srt(vtt_path)

print('Done')
