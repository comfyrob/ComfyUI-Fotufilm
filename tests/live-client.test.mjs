import test from 'node:test';
import assert from 'node:assert/strict';
import {openLivePreview} from '../web/viewer/live-client.js';

test('continuous preview suppresses stale revisions, acknowledges frames and releases decoder on close',()=>{
  const sockets=[],decoders=[],shown=[],closed=[];
  globalThis.location={href:'https://comfy.test/'};
  globalThis.WebSocket=class {static OPEN=1;constructor(){this.readyState=1;this.sent=[];sockets.push(this);}send(x){this.sent.push(JSON.parse(x));}close(){this.readyState=3;}};
  globalThis.EncodedVideoChunk=class{constructor(x){Object.assign(this,x);}};
  globalThis.VideoDecoder=class {constructor(callbacks){this.callbacks=callbacks;decoders.push(this);}configure(){}decode(chunk){this.last=chunk;}close(){this.closed=true;}};
  const live=openLivePreview('/fotufilm/live',{onFrame:(_f,m)=>shown.push(m.frame),onError:e=>{throw e;}});
  const socket=sockets[0];live.update({asset:'a',frame:0});socket.onopen();
  const packet=(seq,revision,reset=false)=>{
    const meta=new TextEncoder().encode(JSON.stringify({revision,frame:seq,timestamp:seq,key:true,reset,codedWidth:32,codedHeight:16}));
    const buffer=new ArrayBuffer(8+meta.length+1),view=new DataView(buffer);view.setUint32(0,seq);view.setUint32(4,meta.length);new Uint8Array(buffer,8,meta.length).set(meta);socket.onmessage({data:buffer});
  };
  packet(1,1,true);live.update({asset:'a',frame:0});
  decoders[0].callbacks.output({timestamp:1,close(){closed.push(1);}});
  assert.deepEqual(shown,[]);assert.ok(socket.sent.some(x=>x.ack===1));
  packet(2,2);decoders[0].callbacks.output({timestamp:2,close(){closed.push(2);}});
  assert.deepEqual(shown,[2]);assert.deepEqual(closed,[1,2]);
  live.close();assert.equal(decoders[0].closed,true);assert.equal(socket.readyState,3);
});

test('gesture updates coalesce while a frame is in flight; release preempts and settles PNG',async()=>{
  let socket;const shown=[],decoders=[];
  globalThis.location={href:'https://comfy.test/'};
  globalThis.WebSocket=class {static OPEN=1;constructor(){socket=this;this.readyState=1;this.sent=[];}send(x){this.sent.push(JSON.parse(x));}close(){this.readyState=3;}};
  globalThis.VideoDecoder=class {constructor(c){this.callbacks=c;decoders.push(this);}configure(){}decode(chunk){this.last=chunk;}close(){}};
  globalThis.EncodedVideoChunk=class{constructor(x){Object.assign(this,x);}};
  globalThis.createImageBitmap=async()=>({close(){}});
  const live=openLivePreview('/live',{onFrame:(_f,m)=>shown.push(m),onError:e=>{throw e;}});
  socket.onmessage({data:JSON.stringify({capabilities:['gesture-h264']})});
  live.update({frame:0,interacting:true});
  for(let i=0;i<30;i++)live.update({frame:0,interacting:true,recipe:{exposure:i/10}});
  assert.equal(socket.sent.length,1);
  live.update({frame:0,interacting:false,recipe:{exposure:3}});
  assert.equal(socket.sent.length,2);assert.equal(socket.sent[1].revision,32);assert.equal(socket.sent[1].interacting,false);
  const packet=async(revision,encoder)=>{
    const meta=new TextEncoder().encode(JSON.stringify({revision,encoder,frame:0,timestamp:revision,key:true,reset:true,codedWidth:32,codedHeight:16}));
    const buffer=new ArrayBuffer(9+meta.length),v=new DataView(buffer);v.setUint32(0,revision);v.setUint32(4,meta.length);new Uint8Array(buffer,8,meta.length).set(meta);
    await socket.onmessage({data:buffer});
  };
  await packet(1,'png');assert.equal(shown.length,0);
  await packet(32,'png');assert.equal(shown.length,1);assert.equal(shown[0].revision,32);
  const metrics=live.getMetrics();assert.equal(metrics.at(-1).status,'drawn');assert.ok(metrics.at(-1).editToDraw>=0);
  assert.equal(metrics[1].status,'superseded');live.close();
});
