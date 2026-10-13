/** Native processing on the server; bounded edits and decoding inside ComfyUI. */
export function openLivePreview(url, {onFrame, onError, onEnded, onStatus}) {
  if (typeof VideoDecoder === 'undefined') throw new Error('Live playback requires WebCodecs. Use a current Chromium browser over HTTPS.');
  const endpoint = new URL(url, location.href);
  endpoint.protocol = endpoint.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(endpoint); socket.binaryType = 'arraybuffer';
  let decoder, latest, revision=0, sentRevision=0, closed=false, timer=0, inFlight=false, lastSent=-Infinity;
  let gestureTransport=false;
  const frames=new Map(), samples=new Map();
  const ack = id => {if(socket.readyState===WebSocket.OPEN)socket.send(JSON.stringify({ack:id}));};
  function flush() {
    clearTimeout(timer);timer=0;
    if(closed||!latest||socket.readyState!==WebSocket.OPEN||latest.revision===sentRevision)return;
    // One gesture revision in flight; keep only the newest unsent controls.
    // A release/non-gesture revision always preempts it immediately.
    if(latest.interacting&&inFlight)return;
    const wait=latest.interacting?Math.max(0,33-(performance.now()-lastSent)):0;
    if(wait){timer=setTimeout(flush,wait);return;}
    sentRevision=latest.revision;inFlight=true;lastSent=performance.now();
    const sample=samples.get(sentRevision);if(sample){sample.sent=lastSent;sample.status='sent';}
    socket.send(JSON.stringify({...latest,interacting:latest.interacting&&gestureTransport}));
  }
  function present(frame,meta) {
    if(meta.revision!==sentRevision||closed)return;
    const sample=samples.get(meta.revision);
    if(sample&&sample.draw===undefined){
      const now=performance.now();
      meta.interaction={editToDraw:now-sample.edited,sendToDraw:now-sample.sent,revision:meta.revision};
      // onFrame draws synchronously. Record completion too, on the same clock.
      onFrame(frame,meta);sample.draw=performance.now();sample.editToDraw=sample.draw-sample.edited;
      sample.sendToDraw=sample.draw-sample.sent;sample.bytes=meta.bytes;sample.server=meta.ms;sample.status='drawn';
    }else onFrame(frame,meta);
    inFlight=false;flush();
  }
  function reset() {
    decoder?.close();decoder=null;
    for(const meta of frames.values())ack(meta.sequence);
    frames.clear();
  }
  function fail(error) {
    if(closed)return;
    onError(error instanceof Error?error:new Error(String(error)));
    closed=true;clearTimeout(timer);reset();socket.close();
  }
  socket.onopen = flush;
  socket.onerror = () => fail(new Error('Live preview connection failed.'));
  socket.onclose = () => {if(!closed)fail(new Error('Live preview disconnected. Reopen Studio to reconnect.'));};
  socket.onmessage = async event => {
    if(closed)return;
    try {
      if(typeof event.data==='string') {
        const status=JSON.parse(event.data);
        if(status.capabilities)gestureTransport=status.capabilities.includes('gesture-h264');
        if(status.error)fail(new Error(status.error));
        if(status.ended&&(status.revision===undefined||status.revision===sentRevision))onEnded?.();
        if(status.revision===sentRevision)onStatus?.(status);
        return;
      }
      const view=new DataView(event.data),sequence=view.getUint32(0),length=view.getUint32(4);
      const meta=JSON.parse(new TextDecoder().decode(new Uint8Array(event.data,8,length)));
      meta.sequence=sequence;meta.bytes=event.data.byteLength;
      const data=new Uint8Array(event.data,8+length);
      if(meta.encoder==='png') {
        // Obsolete PNGs have no decoder dependencies; avoid decode entirely.
        if(meta.revision!==sentRevision){ack(sequence);return;}
        const image=await createImageBitmap(new Blob([data],{type:'image/png'}));
        try {present(image,meta);}finally {image.close();ack(sequence);}
        return;
      }
      if(meta.reset||!decoder) {
        reset();let codec='avc1.42E01F';
        for(let i=2;i<data.length-4;i++) {
          if(data[i-2]===0&&data[i-1]===0&&data[i]===1&&(data[i+1]&31)===7) {
            codec='avc1.'+[...data.slice(i+2,i+5)].map(x=>x.toString(16).padStart(2,'0')).join('');break;
          }
        }
        decoder=new VideoDecoder({output:frame=>{
          const header=frames.get(frame.timestamp);frames.delete(frame.timestamp);
          try {if(header)present(frame,header);}catch(error){fail(error);}
          finally {frame.close();if(header)ack(header.sequence);}
        },error:fail});
        decoder.configure({codec,codedWidth:meta.codedWidth,codedHeight:meta.codedHeight,
                           optimizeForLatency:true,hardwareAcceleration:'prefer-hardware'});
      }
      frames.set(meta.timestamp,meta);
      decoder.decode(new EncodedVideoChunk({type:meta.key?'key':'delta',timestamp:meta.timestamp,data}));
    } catch(error) {fail(error);}
  };
  return {
    update(value) {
      if(closed)return;
      if(latest){const previous=samples.get(latest.revision);if(previous&&!previous.draw)previous.status='superseded';}
      const {editedAt,...wire}=value;
      latest={...wire,revision:++revision};
      samples.set(revision,{revision,edited:editedAt??performance.now(),status:'queued'});
      while(samples.size>120)samples.delete(samples.keys().next().value);
      onStatus?.({phase:'queued',revision});flush();
      return revision;
    },
    getMetrics:()=>[...samples.values()].map(x=>({...x})),
    close() {closed=true;clearTimeout(timer);reset();socket.close();},
  };
}
