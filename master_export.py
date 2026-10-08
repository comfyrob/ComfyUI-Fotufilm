"""Stream a float HDR source through Fotufilm; encode only at final delivery."""
import numpy as np

P3_TO_709 = np.array([[1.2249401, -.2249404, 0], [-.0420569, 1.0420571, 0], [-.0196376, -.0786361, 1.0982735]], dtype=np.float32)
P3_TO_2020 = np.array([[.753833035, .198597369, .047569596], [.045743849, .941777220, .012478931], [-.001210340, .017601717, .983608623]], dtype=np.float32)
HLG_WHITE = (np.exp((.75 - .55991073) / .17883277) + .28466892) / 12
HDR_CEILING = (1 / HLG_WHITE) ** 1.2


def delivery(linear_p3, hdr, knee):
    # Port of Fotufilm PrintEncoding / HLGTransfer (Apache-2.0), matching browser delivery.
    if hdr:
        positive = np.maximum(linear_p3, 0)
        peak = np.max(positive, axis=-1, keepdims=True)
        over = np.maximum(peak - .9, 0)
        rolled = np.where(peak <= .9, peak, .9 + (HDR_CEILING - .9) * over / (over + HDR_CEILING - .9))
        wide = np.maximum((positive * np.divide(rolled, peak, out=np.zeros_like(peak), where=peak > 1e-6)) @ P3_TO_2020.T, 0)
        y = wide @ np.array([.2627, .6780, .0593], dtype=np.float32)
        light = wide * np.where(y > 1e-6, np.maximum(y, 1e-6) ** (-1 / 6), 0)[..., None] * HLG_WHITE
        light = np.clip(light, 0, 1)
        encoded = np.where(light <= 1 / 12, np.sqrt(3 * light), .17883277 * np.log(np.maximum(12 * light - .28466892, 1e-8)) + .55991073)
    else:
        light = linear_p3 @ P3_TO_709.T
        if 0 <= knee < 1:
            over = np.maximum(light - knee, 0)
            light = np.where(light > knee, knee + (1 - knee) * over / (over + 1 - knee), light)
        light = np.clip(light, 0, 1)
        encoded = np.where(light <= .0031308, light * 12.92, 1.055 * light ** (1 / 2.4) - .055)
    return np.rint(np.clip(encoded, 0, 1) * 65535).astype('<u2')


def export_master(bundle_path, recipe, format_id, destination, interrupt=lambda: None):
    from .finish_pipeline import Source, render_clip
    return render_clip(Source(bundle_path), recipe, destination, format_id, interrupt=interrupt)
