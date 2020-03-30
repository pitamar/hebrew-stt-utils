from pydub import AudioSegment
import pysrt
from glob import glob
import re
import os
import shutil
import json
from tqdm import tqdm
from multiprocessing import Pool

language_code = 'iw'
clip_format = 'webm'
out_path = 'manifest'
segments_path = os.path.join(out_path, 'segment_clips')
merge_clips_threshold = 500  # 500 ms
max_merge_duration = 5 * 1000   # 5 seconds
overwrite = False
blacklist = [
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

if overwrite:
    shutil.rmtree(out_path, ignore_errors=True)

os.makedirs(out_path, exist_ok=True)
os.makedirs(segments_path, exist_ok=True)


def filter_sub_text(str):
    result = str
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r"[^אבגדהוזחטיכךלמםנןסעפףצץקרשת' \.,?0-9]", '', result)
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()
    return result


def process_clip(clip_file):
    clip_id = os.path.basename(os.path.dirname(clip_file))

    srt_file = clip_file.replace(f'.{clip_format}', f'.{language_code}.srt')

    if not os.path.exists(srt_file):
        print(f'Could not find {srt_file}')
        return []

    sub_segment_dir_final = os.path.join(segments_path, clip_id)
    if os.path.exists(sub_segment_dir_final):
        return []

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
    acc_sub_texts = []
    clip_manifest_items = []
    for i in range(len(subs)):
        sub = subs[i]

        sub_text = sub.text_without_tags
        sub_text = re.sub('&[^&;]+;', '', sub_text)

        if any(x in sub_text for x in blacklist):
            continue

        sub_start_ms = sub.start.ordinal
        sub_end_ms = sub.end.ordinal

        if sub_end_ms + segment_padding['end'] > clip_duration_ms - audio_truncate['end']:
            break

        if sub_start_ms - segment_padding['start'] < audio_truncate['start']:
            continue

        acc_sub_texts.append(sub_text)
        if acc_sub_start_ms is None:
            acc_sub_start_ms = sub_start_ms

        if i < len(subs) - 1:
            next_sub = subs[i+1]
            time_between_subs = next_sub.start.ordinal - sub.end.ordinal
            new_acc_duration = sub.end.ordinal - acc_sub_start_ms
            if new_acc_duration < max_merge_duration and time_between_subs < merge_clips_threshold:
                continue

        audio_start_ms = acc_sub_start_ms - segment_padding['start']
        audio_end_ms = sub_end_ms + segment_padding['end']
        duration_in_ms = audio_end_ms - audio_start_ms

        sub_text = filter_sub_text(' '.join(acc_sub_texts))

        sub_segment_path = os.path.join(sub_segment_dir, f'{audio_start_ms}-{audio_end_ms}.flac')

        sub_audio = clip_audio[audio_start_ms:audio_end_ms]
        sub_audio.export(sub_segment_path, format='flac')

        manifest_item = {
            'text': sub_text,
            'duration': duration_in_ms / 1000,
            'audio_filepath': sub_segment_path,
            'acc_sub_texts': acc_sub_texts,
        }

        clip_manifest_items.append(manifest_item)

        acc_sub_texts = []
        acc_sub_start_ms = None

    with open(os.path.join(sub_segment_dir, 'clip_manifest.json'), 'w') as f:
        json.dump(clip_manifest_items, f, indent=True, ensure_ascii=False)

    os.rename(sub_segment_dir, sub_segment_dir_final)
    return clip_manifest_items

pool = Pool(8)
clip_files = glob(f'data/**/*.{clip_format}')
pbar = tqdm(total=len(clip_files))
def update(*args):
    pbar.update()

futures = []
for clip_file in clip_files:
    future = pool.apply_async(process_clip, [clip_file], callback=update)
    futures.append(future)

pool.close()
pool.join()

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
