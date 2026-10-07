import importlib
from pathlib import Path

import folder_paths
import nodes
import torch
import torch.nn.functional as F
from comfy_api.latest import InputImpl, io


class FilmFinishHDRPad(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FilmFinishHDRPad', category='Film Finish/HDR',
            inputs=[io.Image.Input('images')],
            outputs=[io.Image.Output('images'), io.Int.Output('width'), io.Int.Output('height'), io.Int.Output('length')])

    @classmethod
    def execute(cls, images):
        if images.ndim != 4 or len(images) == 0 or not torch.isfinite(images).all():
            raise ValueError('Expected a nonempty, finite video frame batch.')
        count, height, width, _ = images.shape
        padded = F.pad(images.permute(0, 3, 1, 2), (0, -width % 32, 0, -height % 32), mode='replicate').permute(0, 2, 3, 1)
        extra = -(count - 1) % 8
        if extra:
            padded = torch.cat((padded, padded[-1:].expand(extra, -1, -1, -1)))
        return io.NodeOutput(padded, padded.shape[2], padded.shape[1], len(padded))


class FilmFinishHDRRestore(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FilmFinishHDRRestore', category='Film Finish/HDR',
            inputs=[io.Image.Input('images'), io.Image.Input('reference')], outputs=[io.Image.Output('hdr_linear')])

    @classmethod
    def execute(cls, images, reference):
        count, height, width, _ = reference.shape
        if images.shape[0] < count or images.shape[1] < height or images.shape[2] < width:
            raise ValueError('HDR reconstruction returned fewer frames or pixels than the source.')
        return io.NodeOutput(images[:count, :height, :width, :3])


class FilmFinishSaveHDRVideo(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FilmFinishSaveHDRVideo', category='Film Finish/HDR', is_output_node=True,
            description='Writes scene-linear RGB as BT.2020 HLG HEVC 10-bit using the pinned LTX encoder. Keeps audio and frame cadence.',
            inputs=[io.Image.Input('images'), io.Float.Input('fps', default=24, min=1, max=120),
                io.String.Input('filename_prefix', default='film-finish-hdr/source'), io.Audio.Input('audio', optional=True),
                io.Combo.Input('linear_primaries', options=['rec709', 'acescg'], default='rec709', optional=True)],
            outputs=[io.Video.Output('video')])

    @classmethod
    def execute(cls, images, fps, filename_prefix, audio=None, linear_primaries='rec709'):
        if images.ndim != 4 or images.shape[-1] != 3 or not torch.isfinite(images).all():
            raise ValueError('Expected finite scene-linear RGB frames.')
        if linear_primaries not in ('rec709', 'acescg'):
            raise ValueError('Expected Rec.709 or ACEScg linear primaries.')
        saver = nodes.NODE_CLASS_MAPPINGS.get('LTXVSaveHLG')
        if saver is None:
            raise ValueError('Install the pinned ComfyUI-LTXVideo dependency with LTXVSaveHLG.')
        package = saver.__module__.rsplit('.', 1)[0]
        hdr_io = importlib.import_module(package + '.hdr_io')
        hdr_color = importlib.import_module(package + '.hdr_color')
        output = Path(folder_paths.get_output_directory()).resolve()
        destination = (output / filename_prefix).resolve()
        if not destination.is_relative_to(output):
            raise ValueError('HDR output must stay inside the ComfyUI output directory.')
        full, name, counter, subfolder, _ = folder_paths.get_save_image_path(filename_prefix, str(output), images.shape[2], images.shape[1])
        filename = f'{name}_{counter:05d}_hlg.mp4'
        path = Path(full) / filename
        frames = images.detach().cpu().float()
        if frames.shape[1] % 2 or frames.shape[2] % 2:
            frames = F.pad(frames.permute(0, 3, 1, 2), (0, frames.shape[2] % 2, 0, frames.shape[1] % 2), mode='replicate').permute(0, 2, 3, 1)
        try:
            primaries = hdr_color.Primaries.ACESCG if linear_primaries == 'acescg' else hdr_color.Primaries.REC709
            hdr_io._encode_hlg_mp4(frames, path, fps=float(fps), audio=audio, primaries=primaries)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return io.NodeOutput(InputImpl.VideoFromFile(str(path)), ui={'files': [
            {'filename': filename, 'subfolder': subfolder, 'type': 'output', 'frames': len(frames), 'fps': fps}]})


class FilmFinishSaveHDRMaster(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FilmFinishSaveHDRMaster', category='Film Finish/HDR', is_output_node=True,
            description='Preserves float EXR masters and generates float Rec.2020 browser proxies. The source video is retained for audio and playback timing only.',
            inputs=[io.Image.Input('images'), io.Video.Input('source'), io.Float.Input('fps', default=24, min=1, max=120),
                io.Combo.Input('color_space', options=['linear-rec709', 'linear-acescg', 'linear-rec2020']),
                io.String.Input('filename_prefix', default='film-finish-hdr/master')], outputs=[])

    @classmethod
    def execute(cls, images, source, fps, color_space, filename_prefix):
        import tempfile
        import comfy.model_management
        from .hdr_master import write_master
        output = Path(folder_paths.get_output_directory()).resolve()
        if not (output / filename_prefix).resolve().is_relative_to(output):
            raise ValueError('HDR output must stay inside the output directory.')
        full, name, counter, subfolder, _ = folder_paths.get_save_image_path(filename_prefix, str(output), images.shape[2], images.shape[1])
        filename = f'{name}_{counter:05d}.ffhdr.zip'
        with tempfile.TemporaryDirectory(prefix='film-hdr-playback-') as directory:
            playback = source.get_stream_source()
            if not isinstance(playback, str):
                path = Path(directory) / 'source.mp4'
                playback.seek(0)
                with path.open('wb') as target:
                    while chunk := playback.read(4 * 1024 * 1024):
                        target.write(chunk)
                playback = str(path)
            write_master(images, fps, color_space, playback, Path(full) / filename,
                         comfy.model_management.throw_exception_if_processing_interrupted)
        return io.NodeOutput(ui={'files': [{'filename': filename, 'subfolder': subfolder, 'type': 'output'}]})


class FotufilmDevelopHDRMaster(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FotufilmDevelopHDRMaster', category='Film Finish', is_output_node=True,
            inputs=[io.String.Input('file'), io.String.Input('recipe_json', multiline=True),
                io.Combo.Input('format', options=['mp4', 'prores422hq', 'hlg'])], outputs=[io.Video.Output('video')])

    @classmethod
    def execute(cls, file, recipe_json, format):
        import json
        import uuid
        import comfy.model_management
        from .master_export import export_master
        source = Path(folder_paths.get_input_directory()).resolve() / file
        if not source.resolve().is_relative_to(Path(folder_paths.get_input_directory()).resolve()) or source.suffix.lower() != '.zip':
            raise ValueError('Choose an uploaded Film Finish HDR master.')
        extension = 'mov' if format == 'prores422hq' else 'mp4'
        path = Path(folder_paths.get_output_directory()) / f'film-finish-{uuid.uuid4().hex}.{extension}'
        export_master(source, json.loads(recipe_json), format, path, comfy.model_management.throw_exception_if_processing_interrupted)
        if format == 'prores422hq':
            from .video_delivery import repair_prores_color
            repair_prores_color(path, 1)
        return io.NodeOutput(InputImpl.VideoFromFile(str(path)), ui={'files': [{'filename': path.name, 'subfolder': '', 'type': 'output'}]})
