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
    ids=[1,2,5,9]+([3] if include_ltx else [])
    nodes=[copy.deepcopy(old[id]) for id in ids]
    graph={k:copy.deepcopy(v) for k,v in original.items() if k not in ('nodes','links','definitions')}
    graph.update(nodes=nodes,links=[],groups=[],extra={'ds':{'scale':.65,'offset':[30,20]}})
    if include_ltx:graph['definitions']=copy.deepcopy(original['definitions'])
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
    byid[9]['pos']=[2100,100]
    byid[5]['pos']=[3300,100]
    byid[5]['title']='Optional · Export finished video'
    byid[5]['widgets_values'][-1]=False
    if include_ltx:byid[3]['pos']=[430,100]
    nodes.extend([
        node(10,'GetVideoComponents',(0,460),[('video','VIDEO')],[('images','IMAGE'),('audio','AUDIO'),('fps','FLOAT')],title='Decode original video'),
        node(11,'RTXTrueHDR',(430,430),[('images','IMAGE')],[('hdr_images','IMAGE')],[100,100,50,650,True,'HDR PQ'],title='NVIDIA · Enhance to HDR',size=(340,300)),
        node(12,'ImageColorSpace',(830,430),[('image','IMAGE')],[('IMAGE','IMAGE')],['HDR PQ','linear'],title='NVIDIA PQ → linear Rec.709'),
        node(13,'ImageColorSpace',(830,780),[('image','IMAGE')],[('IMAGE','IMAGE')],['sRGB','linear'],title='SDR → linear (no HDR generation)'),
        node(15,'FotufilmSelectSource',(1240,360),[('original','IMAGE'),('nvidia','IMAGE'),('ltx','IMAGE')],[('linear_rec709','IMAGE')],['Original SDR'],title='1 · Choose HDR method'),
        node(16,'SaveImageAdvanced',(1240,800),[('images','IMAGE')],[('images','IMAGE')],['fotufilm/source','exr','32-bit float','linear'],title='Optional · Save source EXR sequence'),
        node(17,'FotufilmDevelopFrames',(3300,600),[('images','IMAGE'),('recipe_json','STRING')],[('linear_p3','IMAGE'),('color_space','STRING')],['{}','linear Rec.709',0,'fixed',0],title='Render finished frames'),
        node(18,'FotufilmLinearToRec709',(3700,600),[('images','IMAGE')],[('linear_rec709','IMAGE')],['linear-p3'],title='Finished P3 → linear Rec.709'),
        node(19,'SaveImageAdvanced',(4100,600),[('images','IMAGE')],[('images','IMAGE')],['fotufilm/finished','exr','32-bit float','linear'],title='Optional · Save finished EXR sequence'),
        node(8,'MarkdownNote',(0,1100),widgets=[(ROOT/'docs/hdr-choice-workflow.md').read_text()],title='Start here · Film, color and HDR explained',size=(1000,1000)),
    ])
    if include_ltx:
        nodes.append(node(14,'FotufilmLinearToRec709',(830,100),[('images','IMAGE')],[('linear_rec709','IMAGE')],['linear-acescg'],title='LTX ACEScg → linear Rec.709'))
    byid={n['id']:n for n in nodes}
    byid[16]['mode']=byid[19]['mode']=2  # Mute optional output roots, never bypass them.
    byid[17]['inputs'][1]['widget']={'name':'recipe_json'}
    def connect(a,o,b,i):
        link=len(graph['links'])+1;kind=byid[a]['outputs'][o]['type']
        graph['links'].append([link,a,o,b,i,kind])
        byid[a]['outputs'][o]['links'].append(link);byid[b]['inputs'][i]['link']=link
    links=[(1,0,10,0),(10,0,11,0),(11,0,12,0),(10,0,13,0),(13,0,15,0),(12,0,15,1),
           (1,0,2,0),(15,0,2,1),(10,2,2,2),(1,0,9,0),(15,0,9,1),(10,2,9,2),(2,0,9,3),
           (1,0,5,0),(9,0,5,1),(15,0,5,2),(10,2,5,3),(15,0,16,0),
           (15,0,17,0),(9,0,17,1),(17,0,18,0),(18,0,19,0)]
    if include_ltx:links.extend([(1,0,3,0),(3,0,14,0),(14,0,15,2)])
    for args in links:connect(*args)
    graph['groups']=[dict(id=1,title='1 · Prepare source — only the selected HDR branch runs',bounding=[-30,30,1630,1020],color='#354963',font_size=22,flags={}),
                     dict(id=2,title='2 · Film and color — settings update the shared preview',bounding=[1610,30,1610,1000],color='#384b43',font_size=22,flags={}),
                     dict(id=3,title='3 · Optional outputs — enable only what you want to save',bounding=[3260,30,1250,930],color='#524335',font_size=22,flags={})]
    graph['last_node_id']=max(byid);graph['last_link_id']=len(graph['links'])
    name='Fotufilm - SDR or NVIDIA or LTX HDR - Film + Grade.json' if include_ltx else 'Fotufilm - SDR or NVIDIA HDR - Film + Grade.json'
    (ROOT/'examples'/name).write_text(json.dumps(graph,indent=2)+'\n')


if __name__=='__main__':
    build();build(False)
