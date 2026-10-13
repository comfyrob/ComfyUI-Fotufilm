"""A trial is a range of the original clip, not a lower-quality preview."""
def export_range(info, kind='full', start=0):
    if kind not in ('full', 'trial'):
        raise ValueError('Export range must be full or trial.')
    if type(start) is not int or not 0 <= start < info['frames']:
        raise ValueError('Invalid export start frame.')
    if kind == 'full':
        if start != 0:
            raise ValueError('Full export must start at frame zero.')
        return 0, info['frames']
    return start, min(max(1, round(info['fps'] * 5)), info['frames'] - start)
