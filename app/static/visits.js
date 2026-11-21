const visitUi={busy:false};const feedback=document.querySelector('#feedback');document.querySelector('#source').value=new URL(location.href).searchParams.get('dataset')||document.querySelector('#source').value;document.querySelector('#run').addEventListener('click',async()=>{if(visitUi.busy)return;visitUi.busy=true;feedback.textContent='核验中…';try{const dataset=document.querySelector('#source').value;const r=await fetch(dataset===document.body.dataset.source?'/api/runs/'+document.body.dataset.runId+'/rerun':'/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset})});const data=await r.json();if(!r.ok)throw Error(data.detail);const url=new URL(location.href);url.searchParams.set('dataset',dataset);url.searchParams.set('run_id',data.manifest.run_id);location.href=url;}catch(e){feedback.textContent=e.message;}finally{visitUi.busy=false;}});
const filePicker=document.querySelector('#csv-file');
if(filePicker){
 const editor=document.querySelector('#csv-text');
 filePicker.addEventListener('change',async()=>{const file=filePicker.files[0];if(!file)return;if(file.size>2000000){editor.value='';alert('文件超过2MB，请缩小后导入');return;}const bytes=await file.arrayBuffer();try{editor.value=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch(e){editor.value=new TextDecoder('gb18030',{fatal:true}).decode(bytes);}});
 document.querySelector('#import-csv').addEventListener('click',async event=>{event.target.disabled=true;try{const response=await fetch('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csv_text:editor.value})});const data=await response.json();if(!response.ok)throw Error(data.detail);location.href=location.pathname+'?run_id='+data.manifest.run_id;}catch(e){editor.setCustomValidity(e.message);editor.reportValidity();}finally{event.target.disabled=false;}});
 editor.addEventListener('input',()=>editor.setCustomValidity(''));
}
const recomputeForm=document.querySelector('#recompute-form');
if(recomputeForm){
 const out=document.querySelector('#recompute-feedback');
 recomputeForm.addEventListener('submit',async event=>{
  event.preventDefault();
  const receipt=recomputeForm.receipt_id.value.trim();
  const raw=recomputeForm.overrides.value.trim();
  let overrides={};
  if(raw){try{overrides=JSON.parse(raw);}catch(e){out.textContent='JSON 解析失败：'+e.message;return;}}
  out.textContent='重算中…';
  try{
   const r=await fetch('/api/runs/'+document.body.dataset.runId+'/range-recompute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({receipt_id:receipt,overrides})});
   const data=await r.json();
   if(!r.ok)throw Error(data.detail||('重算失败，已保留旧版分级（'+data.code+'）'));
   const rc=data.recompute||{};
   out.textContent='重算成功：旧批 '+rc.source_run_id+' 已失效，新批 '+data.manifest.run_id+'，同一回执重试不会新增分级。';
   const url=new URL(location.href);url.searchParams.set('run_id',data.manifest.run_id);
   setTimeout(()=>{location.href=url;},1200);
  }catch(e){out.textContent=e.message;}
 });
}

