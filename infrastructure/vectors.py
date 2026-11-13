"""Deterministic stimuli; generated vectors are NOT a recovered filter reference."""
import math
import random
from pathlib import Path
import wave

from results import write_samples


def generate(kind, frames, bits, seed=1):
    if not 2 <= bits <= 32 or frames < 1:
        raise ValueError('bits must be 2..32 and frames must be positive')
    low, high = -(1 << (bits-1)), (1 << (bits-1))-1
    rng = random.Random(seed)
    edge = [0, high, low, -1, 1, high//2, low//2, 0x55 & high, 0x2a & high]
    values = []
    for i in range(frames*2):
        if kind == 'edges': value = edge[i % len(edge)]
        elif kind == 'random': value = rng.randint(low, high)
        elif kind == 'impulse': value = high if i == 0 else low if i == 3 else 0
        elif kind == 'sine': value = round(high * 0.75 * math.sin(2*math.pi*(i//2)/32 + (i%2)*math.pi/2))
        elif kind == 'silence': value = 0
        else: raise ValueError(f'Unknown stimulus {kind}')
        values.append(value)
    return values


def from_wav(path, bits=16, limit_frames=None):
    # Explicitly no resampling, normalization, channel mixing, or inferred model output.
    with wave.open(str(path), 'rb') as stream:
        if stream.getcomptype() != 'NONE' or stream.getsampwidth()*8 != bits or stream.getnchannels() not in (1, 2):
            raise ValueError('WAV must be uncompressed mono/stereo signed PCM at the configured width (16/24/32)')
        if bits not in (16, 24, 32): raise ValueError('WAV import supports signed PCM16/24/32')
        rate, channels = stream.getframerate(), stream.getnchannels()
        raw = stream.readframes(limit_frames or stream.getnframes())
    width = bits//8
    values = [int.from_bytes(raw[i:i+width], 'little', signed=True) for i in range(0,len(raw),width)]
    if channels == 1: values = [v for v in values for _ in range(2)]
    if not values: raise ValueError('Empty WAV input')
    return values, {'sample_rate_hz': rate, 'input_channels': channels,
                    'mono_mapping': 'duplicate to left/right' if channels == 1 else None}


def write_vectors(directory, values, bits):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if len(values) < 2 or len(values) % 2:
        raise ValueError('Stimulus must contain complete stereo frames')
    low, high = -(1 << (bits-1)), (1 << (bits-1))-1
    if any(not low <= v <= high for v in values): raise ValueError('Stimulus value out of range')
    mask = (1 << bits)-1
    (directory/'input.hex').write_text(''.join(f'{v & mask:0{(bits+3)//4}x}\n' for v in values), encoding='ascii')
    write_samples(directory/'input.csv', values)
    return directory/'input.hex', directory/'input.csv'
