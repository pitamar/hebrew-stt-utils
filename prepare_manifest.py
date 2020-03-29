from pydub import AudioSegment
import pysrt
from glob import glob
import re
import os
import shutil
import json
from tqdm import tqdm

language_code = 'iw'
wav_files = glob('data/**/*.wav')
# wav_files = glob('data/3Wa0EoXxF0o/*.wav')


out_path = 'manifest'
segments_path = os.path.join(out_path, 'segment_clips')
merge_clips_threshold = 500

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


manifest = []
for wav_file in tqdm(wav_files):
    wav_id = os.path.basename(os.path.dirname(wav_file))
    srt_file = wav_file.replace('.wav', f'.{language_code}.srt')

    if not os.path.exists(srt_file):
        print(f'Could not find {srt_file}')
        continue

    subs = pysrt.open(srt_file)
    wav_audio = AudioSegment.from_wav(wav_file)

    acc_sub_start_ms = None
    acc_sub_texts = []
    for i in range(len(subs)):
        sub = subs[i]

        sub_start_ms = sub.start.ordinal
        sub_end_ms = sub.end.ordinal

        acc_sub_texts.append(sub.text_without_tags)
        if acc_sub_start_ms is None:
            acc_sub_start_ms = sub_start_ms

        if i < len(subs) - 1:
            next_sub = subs[i+1]
            time_between_subs = next_sub.start.ordinal - sub.end.ordinal
            if time_between_subs < merge_clips_threshold:
                continue

        pad_start = 0
        pad_end = 0
        audio_start_ms = acc_sub_start_ms - pad_start
        audio_end_ms = sub_end_ms + pad_end
        duration = audio_end_ms - audio_start_ms

        sub_text = filter_sub_text(' '.join(acc_sub_texts))
        sub_audio = wav_audio[audio_start_ms:audio_end_ms]

        sub_segment_path = os.path.join(
            segments_path,
            wav_id,
            f'{audio_start_ms}-{audio_end_ms}.wav',
        )
        os.makedirs(os.path.dirname(sub_segment_path), exist_ok=True)
        sub_audio.export(sub_segment_path, format='wav')

        manifest_item = {
            'text': sub_text,
            'audio': sub_segment_path,
            'duration': duration,
            'acc_sub_texts': acc_sub_texts,
        }

        manifest.append(manifest_item)

        acc_sub_texts = []
        acc_sub_start_ms = None

with open(os.path.join(out_path, 'manifest.json'), 'w') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=True)

print('Done')
