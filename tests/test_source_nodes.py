import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

ROOT=Path(__file__).resolve().parents[1]
p=types.ModuleType('film_finish');p.__path__=[str(ROOT)];sys.modules.setdefault('film_finish',p)
from film_finish.source_nodes import FotufilmSelectSource, FotufilmLinearToRec709, METHODS
from film_finish.grading import convert


class SourceTests(unittest.TestCase):
    def test_selector_requests_only_chosen_input_and_returns_same_buffer(self):
        image=torch.tensor([-.1,.18,7.]).expand(2,4,6,3)
        for method,key in METHODS.items():
            self.assertEqual(FotufilmSelectSource.check_lazy_status(method),[key])
            self.assertEqual(FotufilmSelectSource.check_lazy_status(method,**{key:image}),[])
            self.assertIs(FotufilmSelectSource.execute(method,**{key:image}).result[0],image)
        with self.assertRaises(ValueError):FotufilmSelectSource.execute('NVIDIA HDR')

    def test_linear_conversion_preserves_hdr_gamut_alpha_and_input(self):
        rgb=torch.tensor([-.12,.18,8.]).expand(2,4,6,3).clone()
        for space in ('linear-acescg','linear-rec2020','linear-p3'):
            encoded=convert(rgb,'linear-rec709',space)
            alpha=torch.full((*encoded.shape[:-1],1),.37)
            source=torch.cat((encoded,alpha),-1);saved=source.clone()
            result=FotufilmLinearToRec709.execute(source,space).result[0]
            torch.testing.assert_close(result[...,:3],rgb,rtol=2e-5,atol=2e-6)
            torch.testing.assert_close(result[...,3:],alpha)
            torch.testing.assert_close(source,saved)

    def test_real_comfy_executor_does_not_run_unused_branches(self):
        import nodes
        from execution import PromptExecutor
        calls=[];captured=[]
        class Branch:
            @classmethod
            def INPUT_TYPES(cls):return {'required':{'value':('INT',)}}
            RETURN_TYPES=('IMAGE',);FUNCTION='execute'
            def execute(self,value):
                calls.append(value);return (torch.full((1,2,2,3),float(value)),)
        class Sink:
            @classmethod
            def INPUT_TYPES(cls):return {'required':{'images':('IMAGE',)}}
            RETURN_TYPES=();FUNCTION='execute';OUTPUT_NODE=True
            def execute(self,images):captured.append(images[0,0,0,0].item());return ()
        class Server:
            client_id=None
            def send_sync(self,*args,**kwargs):pass
        prompt={str(i):{'class_type':'TestSourceBranch','inputs':{'value':i}} for i in (1,2,3)}
        prompt['4']={'class_type':'FotufilmSelectSource','inputs':{'method':'Original SDR','original':['1',0],'nvidia':['2',0],'ltx':['3',0]}}
        prompt['5']={'class_type':'TestSourceSink','inputs':{'images':['4',0]}}
        with patch.dict(nodes.NODE_CLASS_MAPPINGS,{'TestSourceBranch':Branch,'TestSourceSink':Sink,'FotufilmSelectSource':FotufilmSelectSource}):
            for index,method in enumerate(METHODS,1):
                calls.clear();captured.clear();prompt['4']['inputs']['method']=method
                executor=PromptExecutor(Server(),cache_type=False,cache_args={'ram':0,'ram_inactive':0})
                executor.execute(prompt,f'source-{index}',{},['5'])
                self.assertTrue(executor.success,executor.status_messages)
                self.assertEqual(calls,[index]);self.assertEqual(captured,[float(index)])

    def test_workflow_native_savers_and_ltx_definition(self):
        graph=json.loads((ROOT/'examples/Fotufilm - SDR or NVIDIA or LTX HDR - Film + Grade.json').read_text())
        before=json.loads((ROOT/'examples/Fotufilm - LTX HDR + Film + Color Grade - Modal.json').read_text())
        self.assertEqual(graph['definitions'],before['definitions'])
        byid={n['id']:n for n in graph['nodes']}
        for id,a,o,b,i,t in graph['links']:
            self.assertIn(id,byid[a]['outputs'][o]['links']);self.assertEqual(byid[b]['inputs'][i]['link'],id)
            self.assertEqual(byid[b]['inputs'][i]['type'],t)
        for n in graph['nodes']:
            if n['type']=='SaveImageAdvanced':
                self.assertEqual(n['widgets_values'][1:],['exr','32-bit float','linear']);self.assertEqual(n['mode'],2)
        self.assertEqual(byid[12]['widgets_values'],['HDR PQ','linear'])
        self.assertNotIn('FilmFinishSaveHDRMaster',[n['type'] for n in graph['nodes']])
        self.assertEqual(byid[15]['widgets_values'],['Original SDR'])
