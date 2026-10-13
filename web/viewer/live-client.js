/** Continuous server render stream inside ComfyUI. The browser only decodes it. */
export function openLivePreview(url, {onFrame, onError, onEnded}) {
  if (typeof VideoDecoder === 'undefined') throw new Error('Live playback requires WebCodecs. Use a current Chromium browser over HTTPS.');
  const endpoint = new URL(url, location.href);
  endpoint.protocol = endpoint.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(endpoint);
  socket.binaryType = 'arraybuffer';
  let decoder, latest, revision=0, closed=false;
  const frames = new Map();
  const ack = id => {if(socket.readyState===WebSocket.OPEN)socket.send(JSON.stringify({ack:id}));};
  function reset() {
    decoder?.close();decoder=null;
    for(const meta of frames.values())ack(meta.sequence);
    frames.clear();
  }
  function fail(error) {
    if(closed)return;
    onError(error instanceof Error?error:new Error(String(error)));
    closed=true;reset();socket.close();
  }
  socket.onopen = () => {if(latest)socket.send(JSON.stringify(latest));};
  socket.onerror = () => fail(new Error('Live preview connection failed.'));
  socket.onclose = () => {if(!closed)fail(new Error('Live preview disconnected. Reopen Studio to reconnect.'));};
  socket.onmessage = async event => {
    if(closed)return;
    if(typeof event.data==='string') {
      const status=JSON.parse(event.data);
      if(status.error)fail(new Error(status.error));
      if(status.ended)onEnded?.();
      return;
    }
    try {
      const view=new DataView(event.data),sequence=view.getUint32(0),length=view.getUint32(4);
      const meta=JSON.parse(new TextDecoder().decode(new Uint8Array(event.data,8,length)));
      meta.sequence=sequence;
      const data=new Uint8Array(event.data,8+length);
      if(meta.encoder==='png') {
        const image=await createImageBitmap(new Blob([data],{type:'image/png'}));
        try {if(meta.revision===revision&&!closed)onFrame(image,meta);}
        finally {image.close();ack(sequence);}
        return;
      }
      if(meta.reset||!decoder) {
        reset();
        let codec='avc1.42E01F';
        for(let i=2;i<data.length-4;i++) {
          if(data[i-2]===0&&data[i-1]===0&&data[i]===1&&(data[i+1]&31)===7) {
            codec='avc1.'+[...data.slice(i+2,i+5)].map(x=>x.toString(16).padStart(2,'0')).join('');break;
          }
        }
        decoder=new VideoDecoder({output:frame=>{
          const header=frames.get(frame.timestamp);frames.delete(frame.timestamp);
          try {if(header?.revision===revision&&!closed)onFrame(frame,header);}
          catch(error){fail(error);}
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
    update(value) {if(closed)return;latest={...value,revision:++revision};if(socket.readyState===WebSocket.OPEN)socket.send(JSON.stringify(latest));},
    close() {closed=true;reset();socket.close();},
  };
}
