// Worker opcional. KV REPORTES; secretos REPORT_SALT; variable ALLOWED_ORIGIN.
// Los reportes comunitarios son opiniones: nunca sustituyen automáticamente al canal.
const VIGENCIA=2*3600*1000;
const digest=async s=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)))].map(b=>b.toString(16).padStart(2,'0')).join('');
export default {
 async fetch(request,env){
  const origin=request.headers.get('Origin')||'',allowed=env.ALLOWED_ORIGIN||'';
  const headers={'Content-Type':'application/json;charset=utf-8','Cache-Control':'no-store','Vary':'Origin'};
  if(origin===allowed&&allowed){headers['Access-Control-Allow-Origin']=allowed;headers['Access-Control-Allow-Methods']='GET, POST, OPTIONS';headers['Access-Control-Allow-Headers']='Content-Type';}
  const json=(x,status=200)=>new Response(JSON.stringify(x),{status,headers});
  if(!allowed||!env.REPORT_SALT||!env.REPORTES)return json({error:'Servicio sin configurar'},503);
  if(origin!==allowed)return json({error:'Origen no autorizado'},403);
  if(request.method==='OPTIONS')return new Response(null,{status:204,headers});
  const u=new URL(request.url),now=Date.now();
  try{
   if(request.method==='POST'&&u.pathname==='/reporte'){
    if(Number(request.headers.get('Content-Length')||0)>2048)return json({error:'Solicitud demasiado grande'},413);
    const reader=request.body?.getReader();if(!reader)return json({error:'Faltan datos'},400);
    const chunks=[];let size=0;
    for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>2048){await reader.cancel();return json({error:'Solicitud demasiado grande'},413);}chunks.push(value);}
    let b;try{b=JSON.parse(await new Blob(chunks).text());}catch{return json({error:'JSON no válido'},400);}
    if(b.provincia!=='cienfuegos'||typeof b.circuito_id!=='string'||!/^([CS])-\d{1,4}$/.test(b.circuito_id)||!['on','off'].includes(b.tipo)||typeof b.lugar!=='string'||!b.lugar.trim()||b.lugar.length>100)return json({error:'Datos no válidos'},400);
    const ip=request.headers.get('CF-Connecting-IP');if(!ip)return json({error:'No se pudo verificar el origen'},400);
    const user=await digest(env.REPORT_SALT+':'+new Date(now).toISOString().slice(0,10)+':'+ip);
    // KV es eventualmente consistente: límite orientativo. Para antiabuso estricto, rate limiting de Cloudflare.
    const rateKey='rate:'+user,rate=await env.REPORTES.get(rateKey,'json');
    if(rate&&now-rate.start<3600000&&rate.count>=3)return json({error:'Máximo 3 reportes por hora'},429);
    const next=rate&&now-rate.start<3600000?{start:rate.start,count:rate.count+1}:{start:now,count:1};
    await env.REPORTES.put(rateKey,JSON.stringify(next),{expirationTtl:3600});
    const record={provincia:'cienfuegos',circuito_id:b.circuito_id,lugar:b.lugar.trim(),tipo:b.tipo,timestamp:now};
    // Una opinión vigente por persona/circuito, sin exponer IP ni identificador.
    await env.REPORTES.put('r:cienfuegos:'+b.circuito_id+':'+user,JSON.stringify(record),{expirationTtl:7200});
    return json({ok:true});
   }
   if(request.method==='GET'&&u.pathname==='/reportes'){
    const reportes=[];let cursor;
    do{const page=await env.REPORTES.list({prefix:'r:cienfuegos:',limit:500,cursor});
     const rows=await Promise.all(page.keys.map(k=>env.REPORTES.get(k.name,'json')));
     for(const r of rows)if(r&&now-r.timestamp<VIGENCIA&&r.timestamp<=now)reportes.push(r);
     cursor=page.list_complete?undefined:page.cursor;
     if(reportes.length>=2000)break;
    }while(cursor);
    reportes.sort((a,b)=>b.timestamp-a.timestamp);return json({reportes:reportes.slice(0,2000)});
   }
   return json({error:'No encontrado'},404);
  }catch{return json({error:'Servicio temporalmente no disponible'},503);}
 }
};
