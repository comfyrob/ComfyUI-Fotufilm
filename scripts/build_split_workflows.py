"""Generate additive split-control examples; retain existing workflow files."""
import copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def build(source,target):
    graph=json.loads((ROOT/'examples'/source).read_text())
    nodes=graph['nodes'];film=next(n for n in nodes if n['type']=='FotufilmStudio')
    film.update(type='FotufilmFilmStudio',title='1 · Film Emulation',pos=[900,100],size=[390,420])
    film['properties'].update({'Node name for S&R':'FotufilmFilmStudio','fotufilm_studio_expanded':False})
    recipe=json.loads(film['widgets_values'][0]);recipe['sdr_output']='rolloff';film['widgets_values'][0]=json.dumps(recipe)
    grade=copy.deepcopy(film);grade['id']=max(n['id'] for n in nodes)+1
    grade.update(type='FotufilmColorGrade',title='2 · Color Grade + Viewer',pos=[1380,100],size=[1100,850])
    grade['properties'].update({'Node name for S&R':'FotufilmColorGrade','fotufilm_studio_expanded':True})
    grade['widgets_values'].insert(1,'{}')
    for socket in grade['inputs']:socket['link']=None
    for socket in grade['outputs']:socket['links']=[]
    grade['inputs'].append({'name':'recipe_json','type':'STRING','link':None,'widget':{'name':'recipe_json'}})
    nodes.append(grade)
    def connect(a,slot,b,inp):
        byid={n['id']:n for n in nodes};id=max([0]+[l[0] for l in graph['links']])+1
        kind=byid[a]['outputs'][slot]['type'];graph['links'].append([id,a,slot,b,inp,kind])
        byid[a]['outputs'][slot]['links'].append(id);byid[b]['inputs'][inp]['link']=id
    # Fan out the same source, frame batch and FPS; do not materialize film twice.
    for i,socket in enumerate(film['inputs']):
        if socket.get('link') is not None and socket['name'] in ('video','images','fps','master'):
            link=next(l for l in graph['links'] if l[0]==socket['link']);connect(link[1],link[2],grade['id'],i)
    connect(film['id'],1,grade['id'],len(grade['inputs'])-1)
    for link in graph['links'][:]:
        if link[1]==film['id'] and link[3]!=grade['id'] and link[2] in (1,2):
            film['outputs'][link[2]]['links'].remove(link[0]);grade['outputs'][link[2]]['links'].append(link[0]);link[1]=grade['id']
    for n in nodes:
        if n['type']=='FotufilmDevelopVideo':n['pos']=[2580,100]
        if n['type']=='Note':
            n['widgets_values']=['Load → LTX HDR → Film recipe → Color Grade → optional export.\n\nBoth editors use the same float source and film cache. Film/grade nodes output recipes, not rendered pixel batches. Color Grade overrides look defaults. Save to node commits the connected recipe for queued export.\n\nView controls change only the SDR monitor. SDR output view at 0 EV matches the export transform; HDR range view helps inspect highlights. The viewer is not a true HDR display.\n\nLTX output is linear ACEScg. EXR archival stays optional and follows Remove Padding.'];n['pos']=[450,900]
    graph['last_node_id']=grade['id'];graph['last_link_id']=max(l[0] for l in graph['links'])
    (ROOT/'examples'/target).write_text(json.dumps(graph,indent=2)+'\n')

build('Fotufilm - Studio.json','Fotufilm - Film + Color Grade.json')
build('Film Finish - Studio + LTX 2.5 HDR - Modal INT8.json','Fotufilm - LTX HDR + Film + Color Grade - Modal.json')
