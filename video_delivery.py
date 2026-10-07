from fractions import Fraction
from pathlib import Path

import av


def repair_prores_tags(path, graph, result_node):
    node = graph.get(result_node, {})
    classes = {'FotufilmDevelopHDRMaster': 1, 'FotufilmDevelopVideo': 12}
    primaries = classes.get(node.get('class_type'))
    if primaries is None or node.get('inputs', {}).get('format') != 'prores422hq':
        return
    repair_prores_color(path, primaries)


def repair_prores_color(path, primaries):
    with av.open(str(path)) as source:
        context = source.streams.video[0].codec_context
        if context.name != 'prores':
            raise ValueError('The ProRes export returned an unexpected codec.')
        next(source.decode(video=0))
        if (int(context.color_primaries), int(context.color_trc), int(context.colorspace)) == (primaries, 13, 1):
            return
    import subprocess
    import imageio_ffmpeg
    path = Path(path)
    tagged = path.with_name(path.stem + '-color' + path.suffix)
    try:
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-y', '-i', str(path),
            '-map', '0', '-c', 'copy', '-bsf:v', f'prores_metadata=color_primaries={primaries}:color_trc=13:colorspace=1',
            '-color_primaries', str(primaries), '-color_trc', '13', '-colorspace', '1',
            '-movflags', '+faststart+write_colr', str(tagged)], check=True, capture_output=True, timeout=300)
        tagged.replace(path)
    finally:
        tagged.unlink(missing_ok=True)


def repair_packet_durations(path):
    path = Path(path)
    repaired = path.with_name(path.stem + '-timing' + path.suffix)
    try:
        with av.open(str(path)) as source, av.open(str(repaired), 'w') as target:
            target.metadata.update(source.metadata)
            streams = {stream.index: target.add_stream_from_template(stream) for stream in source.streams}
            for packet in source.demux():
                if packet.dts is None:
                    continue
                rate = packet.stream.base_rate if packet.stream.type == 'video' else None
                if rate and not packet.duration:
                    packet.duration = round(Fraction(1, 1) / rate / packet.time_base)
                packet.stream = streams[packet.stream.index]
                target.mux(packet)
        repaired.replace(path)
    finally:
        repaired.unlink(missing_ok=True)
