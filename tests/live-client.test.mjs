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
