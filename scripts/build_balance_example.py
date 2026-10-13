"""Add explicit correction and still-output branches to the existing HDR example."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'examples/Film Finish - Studio + LTX 2.5 HDR - Modal INT8.json'
g = json.loads(source.read_text())
recipe = (ROOT / 'examples/vision250d-clean.recipe.json').read_text()
byid = {n['id']: n for n in g['nodes']}
# Preserve source model pins and links; insert balance between LTX and consumers.
old = [link for link in g['links'] if link[1] == 3 and link[2] == 0 and link[3] in (2,5)]
balance = dict(id=9,type='FotufilmBalanceFrames',pos=[860,1020],size=[340,410],flags={},order=0,mode=0,
    inputs=[dict(name='images',type='IMAGE',link=None)],
    outputs=[dict(name='linear_acescg',type='IMAGE',links=[],slot_index=0),dict(name='color_space',type='STRING',links=[],slot_index=1)],
    properties={'Node name for S&R':'FotufilmBalanceFrames'},
    widgets_values=['linear ACEScg',True,0,0,0,1,.18,0,0,1,0,0,0,0,1,1,1,1,1,1,0,0,0])
still = dict(id=10,type='FotufilmInspectFrame',title='Optional · Save final still',pos=[2100,560],size=[350,310],flags={},order=0,mode=0,
    inputs=[dict(name='recipe_json',type='STRING',link=None,widget={'name':'recipe_json'}),dict(name='images',type='IMAGE',link=None)],
    outputs=[dict(name='linear_rec2020',type='IMAGE',links=[],slot_index=0),dict(name='color_space',type='STRING',links=[],slot_index=1)],
    properties={'Node name for S&R':'FotufilmInspectFrame'},widgets_values=[0,'finish',recipe,'linear ACEScg',False])
g['nodes'] += [balance,still];byid.update({9:balance,10:still})
for link in old:
    byid[3]['outputs'][0]['links'].remove(link[0]);link[1]=9
    balance['outputs'][0]['links'].append(link[0])
def connect(a,o,b,i,t):
    id=max(x[0] for x in g['links'])+1;g['links'].append([id,a,o,b,i,t])
    byid[a]['outputs'][o]['links'].append(id);byid[b]['inputs'][i]['link']=id
connect(3,0,9,0,'IMAGE');connect(9,0,10,1,'IMAGE');connect(2,1,10,0,'STRING')
byid[8]['widgets_values']=['Optional source correction → Studio → optional saving.\n\nBalance Source uses Gear math on linear HDR frames. Queue after changing it; LTX reuses its cached output when its inputs are unchanged. Studio Before/after compares this corrected input with the finished film look.\n\nStudio color wheels adjust the finished look live. There is no histogram or still-save panel inside Studio.\n\nSave final still is disabled by default. Set its frame, enable, then queue to save one full-resolution EXR with Studio’s recipe. No MP4 round trip.\n\nOlder recipes can already contain an input correction. Studio labels these; clear it there before moving the same settings into Balance Source to avoid applying it twice.\n\nArchive keeps the uncorrected HDR source. The monitor remains SDR.']
byid[8]['size']=[430,450]
g['last_node_id']=10;g['last_link_id']=max(x[0]for x in g['links'])
(ROOT/'examples/Fotufilm - Balance + Studio + optional still - Modal.json').write_text(json.dumps(g,indent=2)+'\n')
