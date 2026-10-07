// Configurar SHEET_ID y ADMIN_TOKEN (aleatorio largo) en Propiedades del script.
// No hay token de Telegram ni contraseñas en el HTML. Sin notificaciones automáticas.
function salida(x){return ContentService.createTextOutput(JSON.stringify(x)).setMimeType(ContentService.MimeType.JSON);}
function seguro(v){v=String(v||'').trim().slice(0,150);return /^[=+@-]/.test(v)?"'"+v:v;}
function autorizado(token){
  const esperado=PropertiesService.getScriptProperties().getProperty('ADMIN_TOKEN')||'';
  if(esperado.length<24||typeof token!=='string'||token.length!==esperado.length)return false;
  let diff=0;for(let i=0;i<esperado.length;i++)diff|=esperado.charCodeAt(i)^token.charCodeAt(i);return diff===0;
}
function doGet(){return salida({error:'Usa POST. La administración requiere autenticación.'});}
function doPost(e){
  try{
    if(!e.postData||e.postData.contents.length>4000)return salida({error:'Solicitud no válida'});
    const data=JSON.parse(e.postData.contents),action=data.action||'enviar';
    const props=PropertiesService.getScriptProperties(),sheetId=props.getProperty('SHEET_ID');
    if(!sheetId)return salida({error:'Servicio sin configurar'});
    const admin=['pendientes','aprobar','rechazar','aprobados'].includes(action);
    if(admin&&!autorizado(data.token))return salida({error:'Acceso denegado'});
    if(!admin&&action!=='enviar')return salida({error:'Acción no válida'});
    const lock=LockService.getScriptLock();if(!lock.tryLock(5000))return salida({error:'Ocupado. Intenta otra vez.'});
    try{
      const sheet=SpreadsheetApp.openById(sheetId).getSheetByName('correcciones');
      if(!sheet)return salida({error:'Falta la hoja correcciones'});
      if(action==='enviar'){
        const lat=data.lat,lng=data.lng;
        if(data.prov!=='cienfuegos'||typeof lat!=='number'||typeof lng!=='number'||!Number.isFinite(lat)||!Number.isFinite(lng)||lat<21.75||lat>22.55||lng< -80.95||lng> -79.95||!/^([CS])-\d{1,4}$/.test(data.circuito||'')||!data.lugar)return salida({error:'Datos no válidos'});
        sheet.appendRow([new Date().toISOString(),data.prov,seguro(data.circuito),seguro(data.lugar),lat,lng,'pendiente']);return salida({ok:true});
      }
      if(action==='pendientes'||action==='aprobados'){
        const rows=sheet.getDataRange().getValues(),estado=action==='pendientes'?'pendiente':'aprobado',out=[];
        for(let i=1;i<rows.length;i++)if(rows[i][6]===estado)out.push({fila:i+1,fecha:rows[i][0],prov:rows[i][1],circuito:rows[i][2],lugar:rows[i][3],lat:rows[i][4],lng:rows[i][5]});
        return salida({ok:true,correcciones:out});
      }
      const fila=data.fila;
      if(!Number.isInteger(fila)||fila<2||fila>sheet.getLastRow())return salida({error:'Fila no válida'});
      if(sheet.getRange(fila,7).getValue()!=='pendiente')return salida({error:'Esta corrección ya fue revisada'});
      sheet.getRange(fila,7).setValue(action==='aprobar'?'aprobado':'rechazado');return salida({ok:true});
    }finally{lock.releaseLock();}
  }catch(err){return salida({error:'No se pudo procesar la solicitud'});}
}
