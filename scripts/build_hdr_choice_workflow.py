"""Source choices and native EXR outputs; preserve the existing LTX subgraph."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def node(id, kind, pos, inputs=(), outputs=(), widgets=(), title=None, size=(340,210)):
    return dict(id=id,type=kind,pos=list(pos),size=list(size),flags={},order=0,mode=0,
                inputs=[dict(name=n,type=t,link=None) for n,t in inputs],
                outputs=[dict(name=n,type=t,links=[],slot_index=i) for i,(n,t) in enumerate(outputs)],
                properties={'Node name for S&R':kind},widgets_values=list(widgets),title=title or kind)


def build(include_ltx=True):
    original=json.loads((ROOT/'examples/Fotufilm - LTX HDR + Film + Color Grade - Modal.json').read_text())
    old={n['id']:n for n in original['nodes']}
    ids=[1,2,9]+([3] if include_ltx else [])
    nodes=[copy.deepcopy(old[id]) for id in ids]
    graph={k:copy.deepcopy(v) for k,v in original.items() if k not in ('nodes','links','definitions')}
    graph.update(nodes=nodes,links=[],groups=[],extra={'ds':{'scale':.65,'offset':[30,20]}})
    if include_ltx:
        graph['definitions']=copy.deepcopy(original['definitions'])
        for subgraph in graph['definitions']['subgraphs']:
            for n in subgraph['nodes']:
                if n['type']=='LTXVHDRDecodePostprocess':
                    n['type']='FotufilmLTXHDRDecode'
                    n['properties']['Node name for S&R']=n['type']
                    n['title']='Decode LTX HDR · Only when selected'
                    n['widgets_values']=n['widgets_values'][:2]
    byid={n['id']:n for n in nodes}
    for n in nodes:
        for i in n.get('inputs',[]):i['link']=None
        for o in n.get('outputs',[]):o['links']=[]
        n['widgets_values']=['linear-rec709' if w=='linear-acescg' else w for w in n['widgets_values']]
    for id in (2,9):
        recipe=json.loads(byid[id]['widgets_values'][0]);recipe['engine']='9242d189b6f8321a27c6f6a345aeb4e5991da569';byid[id]['widgets_values'][0]=json.dumps(recipe)
    for id,kind,label in [(2,'FotufilmFilmEditor','film_settings'),(9,'FotufilmGradeEditor','finished_settings')]:
        n=byid[id];n['type']=kind;n['properties']['Node name for S&R']=kind
        n['inputs']=[dict(name='video',type='VIDEO',link=None),dict(name='images',type='IMAGE',link=None),dict(name='fps',type='FLOAT',link=None,widget={'name':'fps'})]
        if id==9:n['inputs'].append(dict(name='recipe_json',type='STRING',link=None,widget={'name':'recipe_json'}))
        n['outputs']=[dict(name=label,type='STRING',links=[],slot_index=0)]
    byid[1]['pos']=[0,100]
    byid[2]['pos']=[1650,100]
    byid[9]['pos']=[2820,100]
    for id in (2,9):
        byid[id]['size']=[1100,850]
        byid[id]['properties']['fotufilm_studio_expanded']=True
    if include_ltx:byid[3]['pos']=[430,100]
    nodes.extend([
        node(10,'GetVideoComponents',(0,460),[('video','VIDEO')],[('images','IMAGE'),('audio','AUDIO'),('fps','FLOAT')],title='Decode original video'),
        node(11,'RTXTrueHDR',(430,430),[('images','IMAGE')],[('hdr_images','IMAGE')],[100,100,50,650,True,'HDR PQ'],title='NVIDIA · Enhance to HDR',size=(340,300)),
        node(12,'ImageColorSpace',(830,430),[('image','IMAGE')],[('IMAGE','IMAGE')],['HDR PQ','linear'],title='NVIDIA PQ → linear Rec.709'),
        node(13,'ImageColorSpace',(830,780),[('image','IMAGE')],[('IMAGE','IMAGE')],['sRGB','linear'],title='SDR → linear (no HDR generation)'),
        node(15,'ComfySwitchNode',(1240,520),[('on_false','IMAGE'),('on_true','IMAGE')],[('output','IMAGE')],[False],title='Use HDR? · Off = original SDR'),
        node(16,'SaveImageAdvanced',(1240,800),[('images','IMAGE')],[('images','IMAGE')],['fotufilm/source','exr','32-bit float','linear'],title='Optional · Save source EXR sequence'),
        node(17,'FotufilmDevelopFrames',(4020,100),[('images','IMAGE'),('recipe_json','STRING')],[('linear_p3','IMAGE'),('color_space','STRING'),('sdr_images','IMAGE')],['{}','linear Rec.709',0,'fixed',0],title='Render film + color at full resolution'),
        node(18,'FotufilmLinearToRec709',(4420,600),[('images','IMAGE')],[('linear_rec709','IMAGE')],['linear-p3'],title='Finished P3 → linear Rec.709'),
        node(19,'SaveImageAdvanced',(4820,600),[('images','IMAGE')],[('images','IMAGE')],['fotufilm/finished','exr','32-bit float','linear'],title='Optional · Save finished EXR sequence'),
        node(5,'CreateVideo',(4420,100),[('images','IMAGE'),('fps','FLOAT'),('audio','AUDIO')],[('VIDEO','VIDEO')],[24,'auto','sRGB','none'],title='Create finished video · SDR'),
        node(20,'SaveVideo',(4820,100),[('video','VIDEO')],[],['fotufilm/finished','mp4','h264','auto'],title='Optional · Save finished video'),
        node(8,'MarkdownNote',(0,1100),widgets=[(ROOT/'docs/hdr-choice-workflow.md').read_text()],title='Start here · Film, color and HDR explained',size=(1000,1000)),
    ])
    if include_ltx:
        nodes.append(node(14,'FotufilmLinearToRec709',(830,100),[('images','IMAGE')],[('linear_rec709','IMAGE')],['linear-acescg'],title='LTX ACEScg → linear Rec.709'))
        nodes.append(node(21,'ComfySwitchNode',(1240,200),[('on_false','IMAGE'),('on_true','IMAGE')],[('output','IMAGE')],[False],title='Use LTX? · Off = NVIDIA / On = LTX'))
    byid={n['id']:n for n in nodes}
    byid[16]['mode']=byid[19]['mode']=byid[20]['mode']=2  # Mute optional output roots, never bypass them.
    byid[17]['inputs'][1]['widget']={'name':'recipe_json'}
    byid[5]['inputs'][1]['widget']={'name':'fps'}
    def connect(a,o,b,i):
        link=len(graph['links'])+1;kind=byid[a]['outputs'][o]['type']
        graph['links'].append([link,a,o,b,i,kind])
        byid[a]['outputs'][o]['links'].append(link);byid[b]['inputs'][i]['link']=link
    links=[(1,0,10,0),(10,0,11,0),(11,0,12,0),(10,0,13,0),(13,0,15,0),
           (1,0,2,0),(15,0,2,1),(10,2,2,2),(1,0,9,0),(15,0,9,1),(10,2,9,2),(2,0,9,3),
           (17,2,5,0),(10,2,5,1),(10,1,5,2),(5,0,20,0),(15,0,16,0),
           (15,0,17,0),(9,0,17,1),(17,0,18,0),(18,0,19,0)]
    if include_ltx:links.extend([(1,0,3,0),(3,0,14,0),(12,0,21,0),(14,0,21,1),(21,0,15,1)])
    else:links.append((12,0,15,1))
    for args in links:connect(*args)
    graph['groups']=[dict(id=1,title='1 · Prepare source — only the selected HDR branch runs',bounding=[-30,30,1630,1020],color='#354963',font_size=22,flags={}),
                     dict(id=2,title='2 · Film and color — settings update the shared preview',bounding=[1610,30,2340,1000],color='#384b43',font_size=22,flags={}),
                     dict(id=3,title='3 · Native outputs — unmute the save node you need',bounding=[3980,30,1220,930],color='#524335',font_size=22,flags={})]
    graph['last_node_id']=max(byid);graph['last_link_id']=len(graph['links'])
    name='Fotufilm - SDR or NVIDIA or LTX HDR - Film + Grade.json' if include_ltx else 'Fotufilm - SDR or NVIDIA HDR - Film + Grade.json'
    (ROOT/'examples'/name).write_text(json.dumps(graph,indent=2)+'\n')


if __name__=='__main__':
    build();build(False)
