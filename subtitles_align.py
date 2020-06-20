import torch
import pysrt
import torchaudio
import matplotlib.pyplot as plt
from bisect import bisect_right
import math


def create_gaussian_kernel(size, sigma):
    meshgrids = torch.meshgrid(
        [
            torch.arange(size_dim, dtype=torch.float32)
            for size_dim in size
        ]
    )

    kernel = 1
    for dim_size, std, mgrid in zip(size, sigma, meshgrids):
        mean = (dim_size - 1) / 2
        kernel *= 1 / (2 * math.pi * std ** 2) * torch.exp(-((mgrid - mean) / std) ** 2 / 2)

    kernel /= sum(kernel)

    return kernel


def find_silence_points(waveform, sample_rate, threshold=0.020, kernel_size=8193, exp=6, bitdepth=16):
    waveform = waveform[:sample_rate*5]
    input = waveform.to('cuda')
    input = input.abs()
    # input /= input.max()
    input /= (1 << bitdepth) // 2 - 1

    clamped_input = input.clamp(max=threshold * 4)

    kernel = create_gaussian_kernel(size=[kernel_size], sigma=[kernel_size // 4])[None, None, :].to('cuda')

    conv = torch.nn.functional.conv1d(clamped_input, kernel, padding=kernel.numel() // 2)

    conv = (conv + (1 - threshold)) ** exp - (1 - threshold) ** exp
    conv = torch.nn.functional.conv1d(conv, kernel, padding=kernel.numel() // 2)
    filter = (conv < threshold).long()

    padding = torch.tensor([0], dtype=torch.long, device='cuda')
    filter_positive = filter.squeeze() == 1
    filter_negative = torch.cat([filter.squeeze()[1:], padding]) != 1

    falling_edges = (filter_positive & filter_negative).long()
    falling_edges_indexes = (falling_edges == 1).nonzero().flatten().tolist()

    raising_edges = (~filter_positive & ~filter_negative).long()
    raising_edges_indexes = (raising_edges == 1).nonzero().flatten().tolist()

    if (falling_edges_indexes + [float('inf')])[0] < (raising_edges_indexes + [float('inf')])[0]:
        raising_edges_indexes.insert(0, 0)

    if ([float('-inf')] + raising_edges_indexes)[-1] > ([float('-inf')] + falling_edges_indexes)[-1]:
        falling_edges_indexes.append(-1)

    silence_mins = torch.zeros(conv.shape)
    silence_edges = torch.zeros(conv.shape)
    silence_min_points = []
    silence_edge_points = []
    for r, f in zip(raising_edges_indexes, falling_edges_indexes):
        min_index = (r + conv[0, 0, r:f].argmin()).item()
        silence_mins[0, 0, min_index] = 1
        silence_min_points.append(min_index)

        silence_edges[0, 0, r] = 1
        silence_edge_points.append(r)
        silence_edges[0, 0, f] = 1
        silence_edge_points.append(f)

    # torchaudio.save('/tmp/audio-conv.wav', (conv[0] << 31).cpu(), sample_rate)
    # torchaudio.save('/tmp/audio-min-silence.wav', (silence_mins[0] * ((1 << 30) - 1)).cpu(), sample_rate)
    # torchaudio.save('/tmp/audio-edges-silence.wav', (silence_edges[0] * ((1 << 30) - 1)).cpu(), sample_rate)

    return silence_min_points, silence_edge_points


def find_nearest_silence(silence_times, position, window_ms_duration):
    left_index = bisect_right(silence_times, position) - 1
    left_point = silence_times[left_index] if left_index < len(silence_times) else float('inf')
    right_index = left_index + 1
    right_point = silence_times[right_index] if right_index < len(silence_times) else float('inf')

    nearest_point = left_point if abs(position - left_point) < abs(position - right_point) else right_point

    if abs(position - nearest_point) > window_ms_duration // 2:
        return position
    else:
        return nearest_point


def align_subs_by_clip_silences(waveform, sample_rate, subs, window_ms_duration=1000):
    silence_min_points, silence_edges_points = find_silence_points(waveform, sample_rate)
    silence_times = [round(x / (sample_rate / 1000)) for x in silence_edges_points]

    for sub in subs:
        aligned_start = find_nearest_silence(silence_times, sub.start.ordinal, window_ms_duration)
        aligned_end = find_nearest_silence(silence_times, sub.end.ordinal, window_ms_duration)

        sub.start.ordinal = aligned_start
        sub.end.ordinal = aligned_end

    return silence_edges_points


def create_sub_for_silence_points(silence_points, sample_rate, width=0.01):
    items = []
    for i, silence_point in enumerate(silence_points):
        item = pysrt.SubRipItem(i, start=0, end=0, text='S')
        item.start.ordinal = round((silence_point / sample_rate - (width / 2)) * 1000)
        item.end.ordinal = round((silence_point / sample_rate + (width / 2)) * 1000)
        items.append(item)

    srt_file = pysrt.SubRipFile(items=items, eol='\n')
    return srt_file
