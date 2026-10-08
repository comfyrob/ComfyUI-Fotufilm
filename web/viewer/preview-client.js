/** Cancellable native Fotufilm previews; never submits the workflow graph. */
export function createPreviewClient(api) {
  const client=crypto.randomUUID();let closed=false;const jobs=new Set();
  async function request(path,data,signal){
    const response=await api.fetchApi(`/fotufilm/${path}`,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal}:{signal});
    const result=await response.json();if(!response.ok||result.error)throw new Error(result.error||'Preview request failed.');return result;
  }
  const fileURL=file=>file?api.apiURL(`/view?${new URLSearchParams({filename:file.filename,subfolder:file.subfolder||'',type:file.type})}`):'';
  async function cancel(job){try{await request(`jobs/${job}/cancel`,{});}catch{}}
  return {
    fileURL,
    register:file=>request('source',file),
    async render(asset,recipe,{mode='frame',frame=0,edge=960,format='mp4',signal,onProgress,channel='main'}={}){
      if(closed||signal?.aborted)throw new DOMException('Cancelled','AbortError');
      const {job}=await request('preview',{asset,recipe,mode,frame,edge,format,channel,client:`${client}:${channel}`});
      if(signal?.aborted||closed){await cancel(job);throw new DOMException('Cancelled','AbortError');}
      jobs.add(job);const abort=()=>cancel(job);signal?.addEventListener('abort',abort,{once:true});
      try{
        while(!closed&&!signal?.aborted){
          const state=await request(`jobs/${job}`,null,signal);onProgress?.(state);
          if(state.status==='complete')return {...state.result,after:fileURL(state.result.after),before:fileURL(state.result.before)};
          if(state.status==='error')throw new Error(state.error);
          if(state.status==='cancelled')throw new DOMException('Superseded','AbortError');
          await new Promise(resolve=>setTimeout(resolve,mode==='frame'&&channel!=='looks'?80:250));
        }
        throw new DOMException('Cancelled','AbortError');
      }finally{jobs.delete(job);signal?.removeEventListener('abort',abort);if(closed||signal?.aborted)await cancel(job);}
    },
    dispose(){closed=true;for(const job of jobs)cancel(job);jobs.clear();}
  };
}
