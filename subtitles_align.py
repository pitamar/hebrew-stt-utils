import torch
import pysrt
import torchaudio
from bisect import bisect_left
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


def find_silence_points(waveform, sample_rate, threshold=0.05, kernel_size=8193, exp=4):
    input = waveform.to('cuda')
    input = input.abs()
    input /= input.max()

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

    silence_points = []
    for r, f in zip(raising_edges_indexes, falling_edges_indexes):
        min_index = (r + conv[0, 0, r:f].argmin()).item()
        silence_points.append(min_index)

    return silence_points


def find_nearest_silence(silence_points, position, window_size):
    left_index = bisect_left(silence_points, position)
    left_point = silence_points[left_index]
    right_index = left_index + 1
    right_point = silence_points[right_index]

    nearest_point = left_point if abs(position - left_point) < abs(position - right_point) else right_point

    if abs(position - nearest_point) > window_size // 2:
        return position
    else:
        return nearest_point


def align_subs_by_clip_silences(waveform, sample_rate, subs, window_duration=1.0):
    silence_points = find_silence_points(waveform, sample_rate)
    window_size = window_duration * sample_rate

    for sub in subs:
        aligned_start = find_nearest_silence(silence_points, sub.start.ordinal, window_size)
        aligned_end = find_nearest_silence(silence_points, sub.end.ordinal, window_size)

        sub.start.ordinal = aligned_start
        sub.end.ordinal = aligned_end

    return silence_points


def create_sub_for_silence_points(silence_points, sample_rate):
    items = []
    for i, silence_point in enumerate(silence_points):
        item = pysrt.SubRipItem(i, start=0, end=0, text='S')
        item.start.ordinal = (silence_point // sample_rate - 0.1) * 1000
        item.end.ordinal = (silence_point // sample_rate + 0.1) * 1000
        items.append(item)

    srt_file = pysrt.SubRipFile(items=items, eol='\n')
    return srt_file
