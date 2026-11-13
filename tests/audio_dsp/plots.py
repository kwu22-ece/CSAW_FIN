"""Write high-resolution waveform, time-frequency, and attenuation plots."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

from audio_io import FULL_SCALE, RATE
from noise_generator import STOPBAND_HZ


def render(directory, series, spectra, attenuation, taps, metrics):
    directory.mkdir()
    labels = {"clean": "Clean", "noise": "Injected noise", "noisy": "Noisy",
              "software": "Filtered (software)", "hardware": "Filtered (hardware)"}
    colors = dict(zip(labels, ("#28628c", "#c28239", "#885267", "#247c64", "#633fa1")))

    def save(fig, name):
        fig.savefig(directory / name, dpi=220, bbox_inches="tight")
        plt.close(fig)

    views = {name: values for name, values in series.items() if name != "noise"}
    fig, axes = plt.subplots(len(views), 2, sharey=True, figsize=(11, 2.1 * len(views)))
    for (name, values), (full_ax, zoom_ax) in zip(views.items(), axes):
        n = len(values)
        if n > 4000:
            width = (n + 3999) // 4000
            starts = np.arange(0, n, width)
            full_ax.fill_between(starts / RATE, np.minimum.reduceat(values, starts) / FULL_SCALE,
                                 np.maximum.reduceat(values, starts) / FULL_SCALE, color=colors[name])
        else:
            full_ax.plot(np.arange(n) / RATE, values / FULL_SCALE, color=colors[name], lw=0.8)
        zoom_n = min(n, 640)
        zoom_ax.plot(np.arange(zoom_n) / RATE, values[:zoom_n] / FULL_SCALE,
                     color=colors[name], lw=0.8)
        full_ax.set(ylabel=name.title(), xlim=(0, n / RATE), ylim=(-1, 1))
        zoom_ax.set(xlim=(0, zoom_n / RATE))
    axes[0, 0].set_title("Full segment (min/max envelope when downsampled)")
    axes[0, 1].set_title("First 40 ms")
    for ax in axes[-1]:
        ax.set_xlabel("Time (s)")
    fig.supylabel("Amplitude (full scale)", x=0.02)
    fig.tight_layout(rect=(0.035, 0, 1, 1))
    save(fig, "waveforms.png")

    maps = []
    for values in views.values():
        window = min(512, len(values))
        # Bound the number of plotted STFT columns for long recordings.
        hop = max(window // 4, int(np.ceil(len(values) / 1800)))
        starts = np.arange(0, len(values) - window + 1, hop)
        frames = np.lib.stride_tricks.sliding_window_view(values, window)[starts]
        taper = signal.windows.hann(window, sym=False)
        density = np.abs(np.fft.rfft(frames / FULL_SCALE * taper, n=512)) ** 2
        density /= RATE * np.sum(taper ** 2)
        density[:, 1:-1] *= 2
        center = (starts + (window - 1) / 2) / RATE
        time_edges = (center[0] - hop / (2 * RATE), center[-1] + hop / (2 * RATE))
        maps.append((10 * np.log10(np.maximum(density.T, 1e-18)), time_edges))
    peak = max(-50, max(float(np.max(data)) for data, _ in maps))
    fig, axes = plt.subplots(len(views), 1, sharex=True, figsize=(10, 2.25 * len(views)),
                             layout="constrained")
    for (name, values), ax, (data, time_edges) in zip(views.items(), axes, maps):
        half_bin = RATE / 1024
        extent = (*time_edges, -half_bin, RATE / 2 + half_bin)
        im = ax.imshow(data, extent=extent, origin="lower", aspect="auto",
                       interpolation="nearest", vmin=peak - 80, vmax=peak, cmap="magma")
        ax.set(xlim=(0, len(values) / RATE), ylim=(0, RATE / 2))
        ax.set_title(labels[name], loc="left")
        ax.set_ylabel("Hz")
    axes[-1].set_xlabel("Time (s)")
    fig.colorbar(im, ax=axes, label="PSD (dBFS/Hz)")
    save(fig, "spectrograms.png")

    fig, (ax, gain_ax) = plt.subplots(2, 1, sharex=True, figsize=(10, 7), layout="constrained")
    for name, (f, density) in spectra.items():
        ax.plot(f, 10 * np.log10(np.maximum(density, 1e-18)), label=labels[name],
                color=colors[name], lw=0.95)
    f, h = signal.freqz(np.asarray(taps) / FULL_SCALE, worN=4096, fs=RATE)
    gain_ax.plot(f, 20 * np.log10(np.maximum(np.abs(h), 1e-9)),
                 label="Q1.15 coefficient response", color="black", lw=1)
    for name, (f, incoming, outgoing) in attenuation.items():
        good = (incoming >= max(float(np.max(incoming)) * 1e-8, 1e-18)) & (outgoing > 0)
        gain = np.full_like(incoming, np.nan)
        gain[good] = 10 * np.log10(outgoing[good] / incoming[good])
        gain_ax.plot(f, gain, label=labels[name] + " residual / injected",
                     color=colors[name], lw=1)
    for subplot in (ax, gain_ax):
        subplot.axvspan(STOPBAND_HZ, RATE / 2, alpha=0.08, color="black")
        subplot.grid(alpha=0.18)
        subplot.legend(loc="best", fontsize=8)
        subplot.set_xlim(0, RATE / 2)
    ax.set_ylabel("PSD (dBFS/Hz)")
    gain_ax.set(xlabel="Frequency (Hz)", ylabel="Gain (dB)", ylim=(-125, 20))
    save(fig, "frequency.png")

    names, values = [], []
    for name, output in metrics["outputs"].items():
        names.append(labels[name])
        values.append([metrics["input_snr_db"], output["output_snr_db"],
                       output["snr_change_db"], output["stopband_noise_attenuation_db"]])
    if not names:
        names, values = ["Input only"], [[metrics["input_snr_db"], None, None, None]]
    fig, ax = plt.subplots(figsize=(9, 1.65), layout="constrained")
    ax.axis("off")
    table = ax.table(cellText=[["—" if v is None else f"{v:.2f}" for v in row] for row in values],
                     rowLabels=names, colLabels=["Input SNR", "Output SNR", "SNR change",
                                                 "Stopband attenuation"],
                     cellLoc="center", bbox=(0.20, 0.15, 0.80, 0.55))
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    ax.set_title("Noise rejection (dB)")
    save(fig, "performance.png")
