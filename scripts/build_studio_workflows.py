"""Build connected Studio examples from the pinned, validated LTX 2.5 graph."""
import copy
import json
import uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples'
recipe = json.loads((EXAMPLES / 'vision250d-clean.recipe.json').read_text())

def node(id, kind, pos, inputs=(), outputs=(), widgets=(), title=None, size=(320,200)):
    result = dict(id=id,type=kind,pos=list(pos),size=list(size),flags={},order=0,mode=0,
        inputs=[dict(name=n,type=t,link=None) for n,t in inputs],
        outputs=[dict(name=n,type=t,links=[],slot_index=i) for i,(n,t) in enumerate(outputs)],
        properties={'Node name for S&R':kind}, widgets_values=list(widgets))
    if title: result['title']=title
    return result

def connect(graph, a, out, b, inp):
    nodes={n['id']:n for n in graph['nodes']};id=max([0]+[l[0] for l in graph['links']])+1
    graph['links'].append([id,a,out,b,inp,nodes[a]['outputs'][out]['type']])
    nodes[a]['outputs'][out]['links'].append(id);nodes[b]['inputs'][inp]['link']=id

def studio(id=2,pos=(490,120)):
    n=node(id,'FotufilmStudio',pos,[('video','VIDEO'),('rendered_preview','VIDEO'),('enhanced_source','VIDEO')],
        [('source_video','VIDEO'),('recipe_json','STRING'),('studio','FOTUFILM_STUDIO')],[json.dumps(recipe),24],size=(1100,850))
    n['properties']['fotufilm_studio_expanded']=True
    return n

def graph(nodes):
    return dict(id=str(uuid.uuid4()),revision=0,last_node_id=max(n['id']for n in nodes),last_link_id=0,nodes=nodes,links=[],groups=[],config={},extra={'ds':{'scale':.72,'offset':[30,20]}},version=.4)

def save(name,g):
    g['last_link_id']=max([0]+[x[0]for x in g['links']]);(EXAMPLES/name).write_text(json.dumps(g,indent=2)+'\n')

review=lambda id,pos:node(id,'FotufilmStudioReview',pos,[('studio','FOTUFILM_STUDIO'),('rendered','VIDEO'),('enhanced_source','VIDEO')],[('video','VIDEO')],size=(320,160))
source=node(1,'LoadVideo',(50,120),outputs=[('VIDEO','VIDEO')],widgets=[''],size=(340,260))
g=graph([source,studio(),node(3,'FotufilmDevelopVideo',(1700,120),[('video','VIDEO'),('recipe_json','STRING')],[('video','VIDEO'),('resolved_recipe','STRING')],[json.dumps(recipe),1,'fixed','mp4']),review(4,(2100,120))])
for args in [(1,0,2,0),(1,0,3,0),(2,1,3,1),(2,2,4,0),(3,0,4,1)]:connect(g,*args)
save('Fotufilm - Studio.json',g)

# Preserve every model pin and HDR transform from the existing LTX graph.
old=json.loads((EXAMPLES/'Film Finish - LTX 2.5 + Fotufilm.json').read_text())
bytype={n['type']:n for n in old['nodes']}
exclude={'LoadVideo','FilmFinishSaveHDRMaster','FilmFinishSaveHDRVideo','FotufilmDevelopVideo','FotufilmDevelopHDRMaster','PrimitiveString','PrimitiveStringMultiline','Note'}
inner=copy.deepcopy([n for n in old['nodes'] if n['type'] not in exclude]);innerids={n['id']for n in inner};byid={n['id']:n for n in inner}
links=[];nextid=1
for n in inner:
    for i in n.get('inputs',[]):i['link']=None
    for o in n.get('outputs',[]):o['links']=[]

def link(a,o,b,i,t):
    global nextid
    id=nextid;nextid+=1;links.append(dict(id=id,origin_id=a,origin_slot=o,target_id=b,target_slot=i,type=t))
    if a in byid:byid[a]['outputs'][o]['links'].append(id)
    if b in byid:byid[b]['inputs'][i]['link']=id
    return id
for _,a,o,b,i,t in old['links']:
    if a in innerids and b in innerids:link(a,o,b,i,t)
components=bytype['GetVideoComponents']['id'];restore=bytype['FilmFinishHDRRestore']['id']
inlink=link(-10,0,components,0,'VIDEO')
outs=[('hdr_linear','IMAGE',restore,0),('audio','AUDIO',components,1),('fps','FLOAT',components,2)]
subid='3c968edd-9020-4fc0-b40d-c94fa71ec85a'
sub=dict(id=subid,version=1,state=dict(lastGroupId=0,lastNodeId=max(innerids),lastLinkId=nextid+3,lastRerouteId=0),revision=0,config={},name='LTX 2.5 · Reconstruct HDR',
 inputNode={'id':-10,'bounding':[-300,380,180,100]},outputNode={'id':-20,'bounding':[4800,380,180,160]},
 inputs=[dict(id=str(uuid.uuid5(uuid.UUID(subid),'video')),name='video',type='VIDEO',linkIds=[inlink],pos={'0':-100,'1':400})],
 outputs=[dict(id=str(uuid.uuid5(uuid.UUID(subid),name)),name=name,type=t,linkIds=[link(a,o,-20,index,t)],pos={'0':4820,'1':400+index*24}) for index,(name,t,a,o) in enumerate(outs)],widgets=[],nodes=inner,groups=copy.deepcopy(old['groups'][1:5]),links=links,extra={})
master=copy.deepcopy(bytype['FilmFinishSaveHDRMaster']);master.update(id=4,pos=[2100,120],size=[360,270]);master['inputs']=[dict(name=n,type=t,link=None)for n,t in [('images','IMAGE'),('source','VIDEO'),('fps','FLOAT')]];master['outputs']=[dict(name='master',type='FOTUFILM_HDR_MASTER',links=[],slot_index=0)]
# Widget-backed linked values must retain their widget metadata.
master['inputs'][2]['widget']={'name':'fps'}
develop=node(5,'FotufilmDevelopHDRMaster',(2520,120),[('recipe_json','STRING'),('master','FOTUFILM_HDR_MASTER')],[('video','VIDEO')],['',json.dumps(recipe),'mp4'],size=(340,260));develop['inputs'][0]['widget']={'name':'recipe_json'}
hlg=copy.deepcopy(bytype['FilmFinishSaveHDRVideo']);hlg.update(id=6,pos=[2100,460],size=[360,270]);hlg['inputs']=[dict(name=n,type=t,link=None)for n,t in [('images','IMAGE'),('audio','AUDIO'),('fps','FLOAT')]];hlg['inputs'][2]['widget']={'name':'fps'};hlg['outputs']=[dict(name='video',type='VIDEO',links=[],slot_index=0)]
hdr=node(3,subid,(1690,120),[('video','VIDEO')],[(n,t)for n,t,_,_ in outs],size=(340,240),title='LTX 2.5 · Reconstruct HDR');hdr['properties']={}
g=graph([copy.deepcopy(source),studio(),hdr,master,develop,hlg,review(7,(2930,120))]);g['nodes'][0]['outputs'][0]['links']=[];g['definitions']={'subgraphs':[sub]}
for args in [(1,0,2,0),(1,0,3,0),(1,0,4,1),(3,0,4,0),(3,2,4,2),(4,0,5,1),(2,1,5,0),(3,0,6,0),(3,1,6,1),(3,2,6,2),(2,2,7,0),(5,0,7,1),(6,0,7,2)]:connect(g,*args)
note=node(8,'Note',(1690,820),widgets=['ONE CONNECTED GRAPH\n1. Upload your video.\n2. Edit and save the Studio recipe.\n3. Run on a GPU ComfyUI server with the pinned LTX 2.5 models.\n\nLTX preserves float ACEScg → EXR master → Fotufilm. No reupload. Open the LTX subgraph to inspect all stages. Recipe edits do not feed into LTX. Keep the reconstruction seed fixed to reuse ComfyUI cache.\n\nReturn to Studio sends the finished render to the same viewer without a graph cycle. MP4 is an SDR delivery preview; the float HDR master stays separate. HLG output requires an eligible film/print recipe.'],size=(560,300),title='How this graph works')
g['nodes'].append(note);g['last_node_id']=8
save('Film Finish - Studio + LTX 2.5 HDR.json',g)
