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
from argparse import ArgumentParser
import torch
import torchaudio
from languages import LanguageEnglish, LanguageHebrew
from subtitles_align import align_subs_by_clip_silences, create_sub_for_silence_points
import pynvml
import traceback
import time
from utils import srt_to_audacity_labels

torch.multiprocessing.set_start_method('spawn', force=True)

parser = ArgumentParser()
parser.add_argument('--workers', help='Number of processes to run concurrently', type=int, default=1)
parser.add_argument('--language', help='Number of processes to run concurrently', type=str, default='iw')
parser.add_argument('--sample-rate', help='A specific output sample rate', type=int, default=None)

args = parser.parse_args()


num_workers = args.workers
language_code = args.language
clip_formats = ('webm', 'm4a')
out_path = 'manifest'
segments_path = os.path.join(out_path, 'segment-clips')
merge_clips_threshold = 2000  # 2 seconds
max_merge_duration = 10 * 1000   # 10 seconds
max_word_count = 50
output_sample_rate = args.sample_rate
overwrite = False
target_sample_rate = 16000

if language_code == 'en':
    language = LanguageEnglish()
elif language_code == 'iw':
    language = LanguageHebrew()
else:
    raise Exception(f'Unknown language {language_code}')

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


def filter_sub_text(str, language):
    result = str

    # Reject strings with an english letter in it
    # match = re.search(r'[a-zA-Z]', str)
    # if match is not None:
    #     return None

    result = re.sub(r'\(' + r'[^\)]+' r'\)', '', result)  # Remove text in parenthesis
    result = re.sub(r'\[' + r'[^\]]+' r'\]', '', result)  # Remove text in brackets
    result = re.sub(r'\{' + r'[^\}]+' r'\}', '', result)  # Remove text in curly brackets
    result = re.sub(r'\s+', ' ', result)
    result = language.filter_text(result)
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()

    if result == '':
        return None

    return result


def process_clip(clip_file, queue, language):
    try:
        clip_audio_tensor = None
        if torch.cuda.is_available():
            pynvml.nvmlInit()
            cuda_devices = [
                {
                    'name': f'cuda:{i}',
                    'used_memory': pynvml.nvmlDeviceGetMemoryInfo(pynvml.nvmlDeviceGetHandleByIndex(i)).used,
                } for i in range(torch.cuda.device_count())
            ]
            cuda_devices.sort(key=lambda d: d['used_memory'])
            lowest_memory_device = cuda_devices[0]
            device_name = lowest_memory_device['name']
        else:
            device_name = 'cpu'

        device = torch.device(device_name)

        clip_id = os.path.basename(os.path.dirname(clip_file))
        clip_format = re.sub(r'^.+\.(\w+)$', r'\1', clip_file)

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

        queue.put({'action': 'set_description', 'pid': os.getpid(), 'description': f'{device_name} {clip_id}'})

        sub_segment_dir = sub_segment_dir_final + '.tmp'
        if os.path.exists(sub_segment_dir):
            shutil.rmtree(sub_segment_dir)

        if os.path.exists(sub_segment_dir_final):
            os.rename(sub_segment_dir_final, sub_segment_dir)

        os.makedirs(sub_segment_dir, exist_ok=True)

        subs = pysrt.open(srt_file)
        clip_audio = AudioSegment.from_file(clip_file, format=clip_format)
        clip_audio = clip_audio.set_channels(1)
        clip_sample_rate = clip_audio.frame_rate
        scale_factor = target_sample_rate / clip_sample_rate
        clip_audio_tensor = torch.tensor([[clip_audio.get_array_of_samples()]], dtype=torch.float32, device=device)
        clip_audio_tensor = torch.nn.functional.interpolate(clip_audio_tensor, scale_factor=scale_factor, recompute_scale_factor=False)
        silence_points = align_subs_by_clip_silences(waveform=clip_audio_tensor, sample_rate=target_sample_rate, subs=subs, device=device)
        # silence_subs = create_sub_for_silence_points(silence_points, target_sample_rate)

        # silence_srt_file = srt_file.replace('.srt', '.silence.srt')
        # silence_subs.save(silence_srt_file)
        #
        # aligned_srt_file = srt_file.replace('.srt', '.aligned.srt')
        # subs.save(aligned_srt_file)
        #
        # srt_to_audacity_labels(srt_file, srt_file.replace('.srt', '.txt'))
        # srt_to_audacity_labels(aligned_srt_file, aligned_srt_file.replace('.srt', '.txt'))
        # srt_to_audacity_labels(silence_srt_file, silence_srt_file.replace('.srt', '.txt'))

        clip_duration_ms = len(clip_audio)

        acc_sub_start_ms = None
        acc_sub_end_ms = None
        acc_sub_texts = []
        clip_manifest_items = []
        for i in range(len(subs)):
            sub = subs[i]

            sub_text = sub.text_without_tags
            sub_text = re.sub('&[^&;]{1,8};', '', sub_text)

            if any(x in sub_text for x in language.blacklist):
                continue

            sub_start_ms = sub.start.ordinal
            sub_end_ms = sub.end.ordinal

            if sub_end_ms + segment_padding['end'] > clip_duration_ms - audio_truncate['end']:
                break

            if sub_start_ms - segment_padding['start'] < audio_truncate['start']:
                continue

            acc_sub_texts.append(sub_text)
            filtered_sub_text = filter_sub_text(' '.join(acc_sub_texts), language)

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
                    word_count = filtered_sub_text.count(' ') + 1
                    new_acc_duration = sub.end.ordinal - acc_sub_start_ms
                    if (
                        new_acc_duration <= max_merge_duration and
                        time_between_subs <= merge_clips_threshold and
                        word_count <= max_word_count
                    ):
                        continue

            if acc_sub_end_ms is not None:
                filtered_sub_text = filter_sub_text(' '.join(acc_sub_texts), language)

                audio_start_ms = acc_sub_start_ms - segment_padding['start']
                audio_end_ms = acc_sub_end_ms + segment_padding['end']
                duration_in_ms = audio_end_ms - audio_start_ms

                sub_segment_file_name = f'{audio_start_ms}-{audio_end_ms}.wav'

                audio_start = audio_start_ms * (target_sample_rate // 1000)
                audio_end = audio_end_ms * (target_sample_rate // 1000)

                sub_audio_tensor = clip_audio_tensor[0, :, audio_start:audio_end] << 16
                audio_output_path = os.path.join(sub_segment_dir, sub_segment_file_name)
                torchaudio.save(filepath=audio_output_path, src=sub_audio_tensor.cpu(), sample_rate=target_sample_rate, precision=16)

                manifest_item = {
                    'text': filtered_sub_text,
                    'duration': duration_in_ms / 1000,
                    'audio_filepath': os.path.join(sub_segment_dir_final, sub_segment_file_name),
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
    except Exception:
        traceback.print_exc()
    finally:
        if clip_audio_tensor is not None:
            del clip_audio_tensor
        # if torch.cuda.is_available():
        #     torch.cuda.ipc_collect()
        #     torch.cuda.empty_cache()


def update(*args):
    queue.put({'action': 'increment_bar'})


def watch_queue(queue, total, num_workers):
    pbar = tqdm(total=total)
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



if __name__ == '__main__':
    pool = Pool(num_workers)
    manager = Manager()
    queue = manager.Queue()
    clip_files = [clip for clips in [glob(f'data/**/*.{clip_format}') for clip_format in clip_formats] for clip in clips]
    total = len(clip_files)


    watch_queue_thread = Process(target=watch_queue, args=[queue, total, num_workers])
    watch_queue_thread.start()

    futures = []
    for i, clip_file in enumerate(clip_files):
        if num_workers > 1:
            future = pool.apply_async(process_clip, [clip_file, queue, language], callback=update)
            futures.append(future)
        else:
            process_clip(clip_file, queue, language)
            update()

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
