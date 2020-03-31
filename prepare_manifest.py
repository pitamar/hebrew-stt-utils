from pydub import AudioSegment
import pysrt
from glob import glob
import re
import os
import shutil
import json
from tqdm import tqdm
from multiprocessing import Pool, Manager, Process
import yaml
import time
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('--workers', help='Number of processes to run concurrently', type=int, default=1)
parser.add_argument('--language', help='Number of processes to run concurrently', type=str, default='iw')

args = parser.parse_args()

num_workers = args.workers
language_code = args.language
clip_format = 'webm'
out_path = 'manifest'
segments_path = os.path.join(out_path, 'segment_clips')
merge_clips_threshold = 500  # 500 ms
max_merge_duration = 5 * 1000   # 5 seconds
overwrite = False
string_blacklist = [
    'כתוביות:',
    'תכתוב:',
    'לשידור:',
]
segment_padding = {
    'start': 0,
    'end':   0,
}
audio_truncate = {
    'start': 20 * 1000,  # 10 seconds
    'end':   20 * 1000,  # 10 seconds
}

clips_blacklist = []
if os.path.exists('clips_blacklist.yaml'):
    with open('clips_blacklist.yaml') as f:
        clips_blacklist = yaml.safe_load(f)

if overwrite:
    shutil.rmtree(out_path, ignore_errors=True)

os.makedirs(out_path, exist_ok=True)
os.makedirs(segments_path, exist_ok=True)


def filter_sub_text(str):
    result = str

    # Reject strings with an english letter in it
    match = re.search(r'[a-zA-Z]', str)
    if match is not None:
        return None

    result = re.sub(r'\(' + r'[^\)]+' r'\)', '', result)  # Remove text in parenthesis
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r"[^אבגדהוזחטיכךלמםנןסעפףצץקרשת' \.,?0-9]", '', result)
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()
    return result


def process_clip(clip_file, queue):
    clip_id = os.path.basename(os.path.dirname(clip_file))

    if clip_id in clips_blacklist:
        return []

    srt_file = clip_file.replace(f'.{clip_format}', f'.{language_code}.srt')

    if not os.path.exists(srt_file):
        print(f'Could not find {srt_file}')
        return []

    sub_segment_dir_final = os.path.join(segments_path, clip_id)
    if os.path.exists(os.path.join(sub_segment_dir_final, 'clip_manifest.json')):
        with open(os.path.join(sub_segment_dir_final, 'clip_manifest.json')) as f:
            clip_manifest = json.load(f)
            return clip_manifest

    queue.put({'action': 'set_description', 'pid': os.getpid(), 'description': clip_id})

    sub_segment_dir = sub_segment_dir_final + '.tmp'
    if os.path.exists(sub_segment_dir):
        shutil.rmtree(sub_segment_dir)

    if os.path.exists(sub_segment_dir_final):
        os.rename(sub_segment_dir_final, sub_segment_dir)

    os.makedirs(sub_segment_dir, exist_ok=True)

    subs = pysrt.open(srt_file)
    clip_audio = AudioSegment.from_file(clip_file, format=clip_format)
    # wav_audio = AudioSegment.from_wav(clip_file)
    clip_duration_ms = len(clip_audio)

    acc_sub_start_ms = None
    acc_sub_end_ms = None
    acc_sub_texts = []
    clip_manifest_items = []
    for i in range(len(subs)):
        sub = subs[i]

        sub_text = sub.text_without_tags
        sub_text = re.sub('&[^&;]{1,8};', '', sub_text)

        if any(x in sub_text for x in string_blacklist):
            continue

        sub_start_ms = sub.start.ordinal
        sub_end_ms = sub.end.ordinal

        if sub_end_ms + segment_padding['end'] > clip_duration_ms - audio_truncate['end']:
            break

        if sub_start_ms - segment_padding['start'] < audio_truncate['start']:
            continue

        acc_sub_texts.append(sub_text)
        filtered_sub_text = filter_sub_text(' '.join(acc_sub_texts))

        # In case subtitle is rejected
        if filtered_sub_text is None:
            del acc_sub_texts[-1]
        else:
            acc_sub_end_ms = sub_end_ms

            if acc_sub_start_ms is None:
                acc_sub_start_ms = sub_start_ms

            is_last_subtitle = i == len(subs) - 1
            if not is_last_subtitle:
                next_sub = subs[i+1]
                time_between_subs = next_sub.start.ordinal - sub.end.ordinal
                new_acc_duration = sub.end.ordinal - acc_sub_start_ms
                if new_acc_duration < max_merge_duration and time_between_subs < merge_clips_threshold:
                    continue

        if acc_sub_end_ms is not None:
            filtered_sub_text = filter_sub_text(' '.join(acc_sub_texts))

            audio_start_ms = acc_sub_start_ms - segment_padding['start']
            audio_end_ms = acc_sub_end_ms + segment_padding['end']
            duration_in_ms = audio_end_ms - audio_start_ms

            sub_segment_path = os.path.join(sub_segment_dir, f'{audio_start_ms}-{audio_end_ms}.flac')

            sub_audio = clip_audio[audio_start_ms:audio_end_ms]
            sub_audio.export(sub_segment_path, format='flac')

            manifest_item = {
                'text': filtered_sub_text,
                'duration': duration_in_ms / 1000,
                'audio_filepath': sub_segment_path,
                'acc_sub_texts': acc_sub_texts,
            }

            clip_manifest_items.append(manifest_item)

        acc_sub_texts = []
        acc_sub_start_ms = None
        acc_sub_end_ms = None

    with open(os.path.join(sub_segment_dir, 'clip_manifest.json'), 'w') as f:
        json.dump(clip_manifest_items, f, indent=True, ensure_ascii=False)

    os.rename(sub_segment_dir, sub_segment_dir_final)

    queue.put({'action': 'set_description', 'pid': os.getpid(), 'description': None})
    return clip_manifest_items


pool = Pool(num_workers)
manager = Manager()
queue = manager.Queue()
clip_files = glob(f'data/**/*.{clip_format}')
pbar = tqdm(total=len(clip_files))


def update(*args):
    queue.put({'action': 'increment_bar'})


def watch_queue(queue, pbar, num_workers):
    worker_description_dict = {}
    completed = 0

    while True:
        msg = queue.get()

        if msg['action'] == 'quit':
            break
        if msg['action'] == 'increment_bar':
            completed += 1
        elif msg['action'] == 'set_description':
            worker_pid = msg['pid']
            worker_description = msg['description']
            if worker_description is None:
                del worker_description_dict[worker_pid]
            else:
                worker_description_dict[worker_pid] = worker_description

        worker_descriptions_list = (list(worker_description_dict.values()) + ['None'] * num_workers)[:num_workers]

        bar_description = f"[{', '.join(worker_descriptions_list)}]"
        pbar.set_description(bar_description)
        pbar.n = completed


watch_queue_thread = Process(target=watch_queue, args=[queue, pbar, num_workers])
watch_queue_thread.start()

futures = []
for clip_file in clip_files:
    future = pool.apply_async(process_clip, [clip_file, queue], callback=update)
    futures.append(future)

pool.close()
pool.join()

queue.put({'action': 'quit'})
watch_queue_thread.join()

manifest = []
for future in futures:
    manifest.extend(future.get())

with open(os.path.join(out_path, 'manifest.json'), 'w') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=True)

with open(os.path.join(out_path, 'jasper_manifest.json'), 'w') as f:
    for item in manifest:
        obj = {k: v for k, v in item.items() if k in ['text', 'duration', 'audio_filepath']}
        json.dump(obj, f, ensure_ascii=False)
        f.write('\n')

print('Done')
