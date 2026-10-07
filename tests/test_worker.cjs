const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const code=fs.readFileSync(path.join(__dirname,'../worker/worker.js'),'utf8');const worker=(await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))).default;const store=new Map();const env={REPORT_SALT:'sal-prueba-larga-solo-para-tests',ALLOWED_ORIGIN:'https://example.test',REPORTES:{get:async k=>store.has(k)?JSON.parse(store.get(k)):null,put:async(k,v)=>store.set(k,v),list:async({prefix})=>({keys:[...store.keys()].filter(k=>k.startsWith(prefix)).map(name=>({name})),list_complete:true})}};
const post=(b,origin='https://example.test')=>new Request('https://worker.test/reporte',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json','CF-Connecting-IP':'192.0.2.1'},body:JSON.stringify(b)});
const data={provincia:'cienfuegos',circuito_id:'C-31',lugar:'Palmira',tipo:'off'};
assert.equal((await worker.fetch(post(data,'https://bad.test'),env)).status,403);
assert.equal((await worker.fetch(post({...data,provincia:'villa-clara'}),env)).status,400);
for(let i=0;i<3;i++)assert.equal((await worker.fetch(post(data),env)).status,200);
assert.equal((await worker.fetch(post(data),env)).status,429);
const response=await worker.fetch(new Request('https://worker.test/reportes',{headers:{Origin:'https://example.test'}}),env);const j=await response.json();assert.equal(j.reportes.length,1);assert.ok(!JSON.stringify(j).includes('192.0.2.1'));console.log('PASS Worker: origen, provincia, validación, límite, deduplicación y privacidad.');})();
