import copy,json,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1]
p=types.ModuleType('film_finish');p.__path__=[str(ROOT)];sys.modules.setdefault('film_finish',p)
from film_finish.display_transform import encode_sdr,sdr_knee,validate_view
from film_finish.grading import convert
from film_finish.master_export import delivery
from film_finish.stage_nodes import compose_grade,FotufilmColorGrade,FotufilmFilmStudio


class ColorViewTests(unittest.TestCase):
    def test_equivalent_primaries_produce_same_display_and_preserve_float_source(self):
        rec709=np.array([[[.02,.18,.6],[2,3,5],[-.01,.1,.5]]],np.float32)
        expected=encode_sdr(rec709,'linear-rec709')
        for space in ['linear-acescg','linear-rec2020','linear-p3']:
            rgb=convert(rec709,'linear-rec709',space);original=rgb.copy()
            np.testing.assert_allclose(encode_sdr(rgb,space),expected,atol=2e-6)
            np.testing.assert_array_equal(rgb,original)
            tensor=torch.from_numpy(rgb)
            np.testing.assert_allclose(encode_sdr(tensor,space).numpy(),expected,atol=2e-6)

    def test_view_exposure_reveals_highlights_without_editing_source(self):
        rgb=np.array([[[1,2,8]]],np.float32);saved=rgb.copy()
        normal=encode_sdr(rgb,'linear-rec709',knee=1)
        lowered=encode_sdr(rgb,'linear-rec709',knee=1,exposure=-4)
        self.assertTrue(np.all(normal>.99));self.assertLess(lowered[0,0,0],lowered[0,0,1]);self.assertLess(lowered[0,0,1],lowered[0,0,2])
        np.testing.assert_array_equal(rgb,saved)

    def test_output_view_matches_16bit_sdr_delivery_and_is_independent_of_stock(self):
        from film_finish.live_preview import display_rgb
        recipe={'sdr_output':'rolloff'}
        self.assertEqual(sdr_knee(recipe,False),sdr_knee(recipe,True))
        rgb=np.random.default_rng(9).uniform(-.1,8,(8,12,3)).astype(np.float32)
        with patch('torch.cuda.is_available',return_value=False):actual=display_rgb(rgb,.7)
        expected=np.rint(delivery(rgb,False,.7)/257).astype(np.uint8)
        self.assertLessEqual(np.max(np.abs(actual.astype(int)-expected.astype(int))),1)
        self.assertEqual(sdr_knee({},False),1);self.assertEqual(sdr_knee({},True),.7)

    def test_invalid_view_rejected(self):
        for value in [{'exposure':float('nan')},{'exposure':True},{'mode':'HDR'},{'stage':'bad'}]:
            with self.assertRaises(ValueError):validate_view(value)

    def test_look_defaults_and_explicit_adjustments_survive_composition_without_mutation(self):
        recipe=json.loads((ROOT/'examples/vision250d-clean.recipe.json').read_text())
        recipe['grading']={'balance':{'exposure':.2},'finish':{'saturation':.7,'contrast':1.1}}
        result=compose_grade(json.dumps(recipe),'{"exposure":0.5}')
        self.assertEqual(result['grading']['finish']['saturation'],.7)
        self.assertEqual(result['grading']['finish']['contrast'],1.1)
        self.assertEqual(result['grading']['finish']['exposure'],.5)
        self.assertEqual(result['grading']['balance']['exposure'],.2)
        self.assertNotIn('exposure',recipe['grading']['finish'])
        with self.assertRaises(ValueError):compose_grade(json.dumps(recipe),'{"tonemap":"ACES"}')

    def test_v3_schemas_have_distinct_ids_and_separate_saved_adjustments(self):
        film=FotufilmFilmStudio.define_schema();grade=FotufilmColorGrade.define_schema()
        self.assertEqual(film.node_id,'FotufilmFilmStudio');self.assertEqual(grade.node_id,'FotufilmColorGrade')
        self.assertNotIn('adjustments_json',[x.id for x in film.inputs])
        self.assertIn('adjustments_json',[x.id for x in grade.inputs])

    def test_new_examples_connect_final_grade_to_export_and_keep_ltx_pins(self):
        old=json.loads((ROOT/'examples/Film Finish - Studio + LTX 2.5 HDR - Modal INT8.json').read_text())
        new=json.loads((ROOT/'examples/Fotufilm - LTX HDR + Film + Color Grade - Modal.json').read_text())
        self.assertEqual(new['definitions'],old['definitions'])
        byid={n['id']:n for n in new['nodes']}
        export=next(n for n in new['nodes'] if n['type']=='FotufilmDevelopVideo')
        link=next(l for l in new['links'] if l[0]==next(i['link'] for i in export['inputs'] if i['name']=='recipe_json'))
        self.assertEqual(byid[link[1]]['type'],'FotufilmColorGrade')
        for id,a,o,b,i,t in new['links']:
            self.assertIn(id,byid[a]['outputs'][o]['links']);self.assertEqual(byid[b]['inputs'][i]['link'],id)
            self.assertEqual(byid[b]['inputs'][i]['type'],t)

class LiveStageTests(unittest.TestCase):
    def test_source_view_skips_film_and_grade_and_view_edits_reuse_developed_frame(self):
        import tempfile,struct,io
        from PIL import Image
        from film_finish.live_preview import LiveRenderer
        from film_finish.preview_runtime import PreviewRuntime
        from film_finish.grading import validate_grading
        calls=[]
        class Source:
            info={'width':8,'height':6,'frames':2,'fps':24,'colorSpace':'linear-acescg'}
            def frames(self,start=0,edge=None):
                for i in range(start,2):yield i,np.full((6,8,3),.18,np.float32)
        class FakeFinisher:
            def __init__(self,recipe,*args):
                self.film_signature='same-film';self.hdr=False;self.grading=validate_grading(recipe.get('grading'))
            def develop(self,rgb,index):calls.append(index);return convert(rgb,'linear-rec2020','linear-p3')
            def close(self):pass
        recipe=json.loads((ROOT/'examples/vision250d-clean.recipe.json').read_text());recipe['sdr_output']='rolloff'
        with tempfile.TemporaryDirectory() as directory,patch('film_finish.live_preview.Finisher',FakeFinisher):
            runtime=PreviewRuntime(Path(directory),'test');renderer=LiveRenderer({'source':Source(),'fingerprint':'test'},1280,runtime)
            try:
                renderer.render(recipe,0,False,1,still=True,view={'stage':'source'})
                self.assertEqual(calls,[]);self.assertIsNone(runtime._engine)
                renderer.render(recipe,0,True,2,still=True)
                recipe['grading']={'finish':{'exposure':.5}}
                packet=renderer.render(recipe,0,True,3,still=True,view={'comparison':'film','exposure':-1})
                self.assertEqual(calls,[0])
                length=struct.unpack('!I',packet[:4])[0];meta=json.loads(packet[4:4+length])
                pixels=np.array(Image.open(io.BytesIO(packet[4+length:])))
                self.assertGreater(pixels[:,:8].mean(),pixels[:,8:].mean())
                self.assertEqual(meta['view']['exposure'],-1)
            finally:renderer.close();runtime.close()
