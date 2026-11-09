"use strict";
const $=id=>document.getElementById(id);let benchmarks=[],providers=[],records=[],csrf='',previewURL='',imageReady=false,imageChecking=false,validationSerial=0,uploadRunning=false;
const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
let feedbackId='',feedbackState=null,feedbackBusy=false,selectionGeneration=0,recoveryToken='';
const selectionMatches=(generation,id)=>generation===selectionGeneration&&id===feedbackId;
const validRecovery=token=>typeof token==='string'&&/^[a-f0-9]{32}\.[A-Za-z0-9_-]{43}$/.test(token);
function clearRecovery(){recoveryToken='';$('recovery-display').value='';$('recovery-display-wrap').hidden=true;$('recovery-input').value='';}
function presentRecovery(response,requested){
 if(!requested||response.save_recovery_token!==true||!validRecovery(response.recovery_token))return;
 if(location.protocol!=='https:'){$('recovery-status').textContent='Private recovery codes are not displayed over HTTP. Use server-owner assistance if this local session is lost.';return;}
 $('session-recovery').open=true;recoveryToken=response.recovery_token;$('recovery-display').value=recoveryToken;$('recovery-display-wrap').hidden=false;
 $('recovery-status').textContent='Save this private recovery code securely now. It grants access to your retained submissions. Recovery rotates it; replace any older saved code.';updateRunState();
}
$('copy-recovery').addEventListener('click',async()=>{
 if(!recoveryToken||location.protocol!=='https:'||feedbackBusy||uploadRunning)return;
 const generation=selectionGeneration,token=recoveryToken;
 try{await navigator.clipboard.writeText(token);if(generation===selectionGeneration&&token===recoveryToken)$('recovery-status').textContent='Copied private recovery code. Store it securely; do not share it or put it in a URL.';}
 catch(err){if(generation===selectionGeneration&&token===recoveryToken)$('recovery-status').textContent='Clipboard unavailable. Select and copy the displayed code manually to secure storage.';}
});
window.addEventListener('pagehide',clearRecovery);
$('recovery-form').addEventListener('submit',recoverSession);
async function recoverSession(event){
 event.preventDefault();if(uploadRunning||feedbackBusy)return;
 if(location.protocol!=='https:'){$('recovery-status').textContent='Recovery requires HTTPS. Contact the server owner for local recovery assistance.';return;}
 const token=$('recovery-input').value;$('recovery-input').value='';
 if(!validRecovery(token)){$('recovery-status').textContent='Enter the exact private recovery code; an annotation ID alone is not proof of ownership.';return;}
 const generation=++selectionGeneration;feedbackId='';feedbackState=null;feedbackBusy=true;renderFeedback();$('label-panel').hidden=true;$('user-label').value='';$('label-note').value='';$('recovery-status').textContent='Recovering session…';
 let accepted=false;
 try{
  const session=await api('/api/session');if(generation!==selectionGeneration)return;
  if(typeof session.csrf_token!=='string'||!session.csrf_token)throw Error('Fresh session could not be verified.');csrf=session.csrf_token;
  const recovered=await api('/api/recovery',{method:'POST',headers:{'X-CSRF-Token':csrf,'Content-Type':'application/json'},body:JSON.stringify({recovery_token:token})});
  if(generation!==selectionGeneration)return;accepted=true;
  if(typeof recovered.csrf_token!=='string'||!recovered.csrf_token||!validRecovery(recovered.recovery_token)||recovered.save_recovery_token!==true)throw Error('Recovery response could not be verified.');
  csrf=recovered.csrf_token;presentRecovery(recovered,true);
  await refreshOwnedFeedback(generation,'');if(generation!==selectionGeneration)return;
  $('recovery-status').textContent='Recovered session and verified retained-submission access. Save the replacement code shown below; the previous code no longer works. No model was updated.';
 }catch(err){if(generation===selectionGeneration){if(accepted)csrf='';$('recovery-status').textContent=accepted?'Recovery accepted but readback could not be verified. Keep the replacement code if shown, refresh, or contact the server owner.':err.message+' Use server-owner assistance if recovery is unavailable.';}}
 finally{feedbackBusy=false;renderFeedback();}
}
// Browser form restoration must never pre-authorize retention for a fresh page.
$('retention-consent').checked=false;
window.addEventListener('pageshow',()=>{$('retention-consent').checked=false;});
const pct=v=>v==null?'Unknown':(100*v).toFixed(1)+'%';const ratio=(n,d)=>n==null?'Unknown':n+'/'+(d||22);
async function api(path,options){const response=await fetch(path,{credentials:'same-origin',cache:'no-store',...options});const body=await response.json();if(!response.ok)throw Error(body.error||'Request failed');return body;}
function clear(node){node.replaceChildren();}
function showError(message){$('global-error').hidden=false;$('global-error').textContent=message;}
function cost(m){const low=m.usd_per_submitted_image_low,high=m.usd_per_submitted_image_high;return low==null||high==null?'Unknown':('$'+low.toFixed(6)+'–'+high.toFixed(6));}
function support(m){if(m.reuses_variant)return 'Historical routing analysis only';if(m.family!=='custom-local')return 'Live rubric / preserved benchmark';if(['custom-resnet18-baseline','custom-refined-mobilenet_v3_large_full','custom-v2-clip_224'].includes(m.method))return 'Saved final head ≠ CV replay';return 'Historical-only CV variant';}
function paintBudget(b){
 const money=b.monetary_limit_removed?'Monetary cap removed (not unlimited requests)':('USD '+(b.additional_approved_usd??'unknown')+' additional approved');
 const planning=b.additional_planning_high_usd==null?'unknown':'$'+b.additional_planning_high_usd.toFixed(6);
 $('budget').textContent=(b.live_snapshot?'LIVE READ-ONLY BUDGET':'BUDGET UNAVAILABLE')+' · '+(b.used??'Unknown')+'/'+b.lifetime_cap+' lifetime requests · '+(b.remaining??'Unknown')+' remaining · '+money+' · planning high '+planning+'. Exact invoice unknown. '+(b.note||'');
}
async function refreshMetadata(generation=selectionGeneration){const metadata=await api('/api/methods');if(generation!==selectionGeneration)return;providers=metadata.methods;paintBudget(metadata.budget);renderProviders(true);}
function table(){
 const query=$('search').value.toLowerCase(),family=$('family').value,sort=$('sort').value;
 const rows=benchmarks.filter(m=>(m.method+' '+m.evaluation).toLowerCase().includes(query)&&(!family||m.family===family)).sort((a,b)=>sort==='method'?a.method.localeCompare(b.method):sort==='unsafe_good_of_bad'?(a[sort]??99)-(b[sort]??99):(b[sort]??-1)-(a[sort]??-1));
 clear($('benchmark-rows'));$('visible-count').textContent=rows.length+' / '+benchmarks.length+' methods';
 for(const m of rows){const tr=el('tr'),td=el('td'),details=el('details');details.append(el('summary',m.method),el('span',m.family,'tag'));
 details.append(el('p',(m.evaluation||'Evaluation unspecified')+'\nSource: '+(m.source||'Frozen cloud benchmark')+'\nLatency: '+(m.latency_scope||'No measured comparable request latency in summary.')+'\nCost: '+(m.cost_note||'Retail bounds when known; failed/unknown attempts are not zero.')+'\nOperational local policy: review required, no safety certification.'));
 td.append(details);tr.append(td);
 const values=[[pct(m.accuracy_binary),ratio(m.correct_binary,m.binary_n)],[pct(m.accepted_accuracy),'accepted binary only'],[pct(m.binary_coverage),'diagnostic / raw'],[ratio(m.unsafe_good_of_bad,m.bad_n||13),m.unsafe_good_of_bad?'unsafe error':''],[ratio(m.review_rejected,m.source_review_n||2),m.review_rejected==null?'not measured':'review-only'],[m.mean_latency_seconds==null?'Unknown':m.mean_latency_seconds.toFixed(2)+' s','see scope'],[cost(m),m.family==='custom-local'?'API $0; compute unknown':'retail, not invoice'],[support(m),'Current upload ≠ historical score']];
 for(let i=0;i<values.length;i++){const cell=el('td'),metric=el('div',values[i][0],'metric');metric.append(el('small',values[i][1]));if(i===3&&m.unsafe_good_of_bad)metric.classList.add('unsafe');cell.append(metric);tr.append(cell);} $('benchmark-rows').append(tr);}
}
function scatter(){const svg=$('scatter'),ns='http://www.w3.org/2000/svg';clear(svg);const s=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;svg.append(n);return n;};
 for(let v=0;v<=100;v+=25){const x=48+v*5.5,y=247-v*2.05;s('line',{x1:48,y1:y,x2:598,y2:y,stroke:'#e4e9eb'});s('text',{x:38,y:y+4,'text-anchor':'end',fill:'#697a83','font-size':10},v+'%');s('text',{x,y:265,'text-anchor':'middle',fill:'#697a83','font-size':10},v+'%');}
 s('text',{x:320,y:286,'text-anchor':'middle',fill:'#697a83','font-size':10},'RAW BINARY COVERAGE →');s('text',{x:48,y:18,fill:'#697a83','font-size':10},'OVERALL ACCURACY');
 benchmarks.forEach((m,i)=>{if(m.accuracy_binary==null||m.binary_coverage==null)return;const color=m.unsafe_good_of_bad?'#b94237':m.family==='custom-local'?'#287b78':'#596ea7';const n=s('circle',{cx:48+m.binary_coverage*550+(i%3-1)*3,cy:247-m.accuracy_binary*205+(i%2)*3,r:5,fill:color,opacity:.75,tabindex:0,role:'img','aria-label':m.method+': '+pct(m.accuracy_binary)+' overall; '+pct(m.binary_coverage)+' coverage; '+m.unsafe_good_of_bad+' unsafe / 13'});const title=document.createElementNS(ns,'title');title.textContent=n.getAttribute('aria-label');n.append(title);});}
function renderProviders(preserve=false){const selected=new Set([...document.querySelectorAll('input[name=provider]:checked')].map(n=>n.value));clear($('provider-list'));for(const p of providers){const label=el('label',undefined,'provider'),input=el('input');input.type='checkbox';input.value=p.id;input.name='provider';input.disabled=p.status!=='available'||uploadRunning||feedbackBusy;input.checked=p.status==='available'&&(preserve?selected.has(p.id):!p.paid);const text=el('span');text.append(el('strong',p.label),el('small',p.status.toUpperCase()+(p.paid?' · PAID REMOTE':' · LOCAL')+' · '+(p.reason||'Configured adapter; explicit consent required for remote inference.')));label.append(input,text);$('provider-list').append(label);}updateRunState();}
function images(){const method=$('image-method').value,index=$('image-index').value;clear($('image-rows'));for(const r of records.filter(r=>r.variant===method&&(!index||String(r.index)===index))){const tr=el('tr');for(const [text,cls]of [[String(r.index)+(r.flagged_label?' · flagged':''),''],[r.sha256||'Not recorded','hash'],[r.truth||'Unknown',''],[r.prediction||'Unknown',r.truth==='bad'&&r.prediction==='good'?'unsafe':''],[(r.population||'')+' / '+(r.reason||''),'']])tr.append(el('td',text,cls));$('image-rows').append(tr);} }
async function upload(event){event.preventDefault();$('global-error').hidden=true;const file=$('image').files[0],selected=[...document.querySelectorAll('input[name=provider]:checked')].map(n=>n.value);if(uploadRunning||feedbackBusy)return showError('Wait for the current upload or annotation operation to finish.');if(!csrf||imageChecking||!imageReady)return showError('Choose a fully decoded image within the size and pixel limits.');if(!file||!selected.length)return showError('Choose an image and at least one available method.');if(file.size>5*1024*1024)return showError('Image exceeds 5 MB.');if(selected.some(id=>!providers.some(p=>p.id===id&&p.status==='available')))return showError('Choose only available methods.');if(selected.some(id=>providers.find(p=>p.id===id).paid)&&!$('paid-consent').checked)return showError('Paid remote methods require explicit consent.');
 const form=new FormData();form.append('image',file);form.append('methods',JSON.stringify(selected));form.append('paid_consent',String($('paid-consent').checked));form.append('retention_consent',String($('retention-consent').checked));const generation=++selectionGeneration;$('label-panel').hidden=true;feedbackId='';feedbackState=null;uploadRunning=true;updateRunState();clear($('results'));$('job-status').textContent='Submitting validated image…';
 try{const accepted=await api('/api/infer',{method:'POST',headers:{'X-CSRF-Token':csrf},body:form});if(generation!==selectionGeneration)return;presentRecovery(accepted,$('retention-consent').checked);let job;
 do{job=await api('/api/jobs/'+accepted.job_id);if(generation!==selectionGeneration)return;$('job-status').textContent=job.status.toUpperCase()+' · '+Object.entries(job.method_statuses).map(([id,s])=>(providers.find(p=>p.id===id)?.label||id)+': '+s).join(' / ');clear($('results'));
 for(const [id,value]of Object.entries(job.results)){const card=el('article',undefined,'result-card');card.append(el('h3',providers.find(p=>p.id===id)?.label||id));if(value.needs_review)card.append(el('span','REVIEW REQUIRED','review'));if(value.diagnostic_binary_prediction)card.append(el('p','Diagnostic binary: '+value.diagnostic_binary_prediction+' · not safety clearance'));else if(value.prediction)card.append(el('p','Visual classification: '+value.prediction+' · not roadworthiness certification'));if(value.error)card.append(el('p',value.error,'unsafe'));const detail=el('details');detail.append(el('summary','Actual result / provenance'),el('pre',JSON.stringify(value,null,2)));card.append(detail);$('results').append(card);}
 if(['queued','running','pending'].includes(job.status))await new Promise(resolve=>setTimeout(resolve,1000));if(generation!==selectionGeneration)return;}while(['queued','running','pending'].includes(job.status));
 feedbackId=accepted.job_id;feedbackState=job.feedback;$('label-panel').hidden=false;$('label-note').value='';$('user-label').value='';$('label-status').textContent=job.feedback_error||'';renderFeedback();await refreshOwnedFeedback();
 }catch(err){if(generation===selectionGeneration){$('job-status').textContent='ERROR · '+err.message;showError(err.message);}}finally{try{await refreshMetadata(generation);}catch(err){if(generation===selectionGeneration)showError('Budget refresh failed: '+err.message);}uploadRunning=false;updateRunState();}}
function updateRunState(){
 const busy=uploadRunning||feedbackBusy;
 $('run').disabled=busy||imageChecking||!imageReady||!csrf;$('image').disabled=busy;
 for(const id of ['paid-consent','retention-consent','owned-feedback'])$(id).disabled=busy;
 for(const input of document.querySelectorAll('input[name=provider]'))input.disabled=busy||!providers.some(p=>p.id===input.value&&p.status==='available');
 const inactive=busy||!feedbackState?.retained;
 for(const id of ['user-label','label-note','save-label','revoke-retention'])$(id).disabled=inactive;
 $('recover-session').disabled=busy||location.protocol!=='https:'; $('recovery-input').disabled=busy||location.protocol!=='https:';
 $('copy-recovery').disabled=busy||!recoveryToken||location.protocol!=='https:';
}
$('image').addEventListener('change',async()=>{
 if(uploadRunning||feedbackBusy)return;const serial=++validationSerial;if(previewURL)URL.revokeObjectURL(previewURL);imageReady=false;const file=$('image').files[0];imageChecking=Boolean(file);$('preview-wrap').hidden=!file;$('global-error').hidden=true;updateRunState();
 try{
  if(!file)return;
  if(file.size>5*1024*1024)throw Error('Image exceeds 5 MB.');
  if(!['image/jpeg','image/png','image/webp'].includes(file.type))throw Error('Use JPEG, PNG or WebP.');
  previewURL=URL.createObjectURL(file);$('preview').src=previewURL;$('file-label').textContent=file.name+' · '+(file.size/1024).toFixed(0)+' KB';
  await $('preview').decode();if(serial!==validationSerial)return;
  if($('preview').naturalWidth*$('preview').naturalHeight>16000000)throw Error('Image exceeds 16 MP.');
  imageReady=true;
 }catch(err){if(serial===validationSerial)showError(err.message||'Image could not be decoded; choose another file.');}
 finally{if(serial===validationSerial){imageChecking=false;updateRunState();}}
});
updateRunState();
for(const id of ['search','family','sort'])$(id).addEventListener('input',table);for(const id of ['image-method','image-index'])$(id).addEventListener('change',images);$('inference-form').addEventListener('submit',upload);
(async()=>{try{const [summary,metadata,evidence,session]=await Promise.all([api('/api/benchmarks'),api('/api/methods'),api('/api/per-images'),api('/api/session')]);benchmarks=summary.methods;providers=metadata.methods;records=evidence.rows;csrf=session.csrf_token;$('method-count').textContent=benchmarks.length;$('evidence-source').textContent=summary.source;
 const best=benchmarks.find(m=>m.method==='custom-v2-clip_224'),nested=benchmarks.find(m=>m.method==='custom-v2-nested_architecture');$('best-local').textContent=best?ratio(best.correct_binary,best.binary_n):'Not recorded';$('nested-local').textContent=nested?ratio(nested.correct_binary,nested.binary_n):'Not recorded';
 for(const f of [...new Set(benchmarks.map(m=>m.family))].sort()){const option=el('option',f);option.value=f;$('family').append(option);}for(const method of [...new Set(records.map(r=>r.variant))].sort()){const option=el('option',method);option.value=method;$('image-method').append(option);}for(const i of [...new Set(records.map(r=>r.index))].sort((a,b)=>a-b)){const option=el('option','Photo '+i);option.value=i;$('image-index').append(option);}$('record-count').textContent=records.length+' records';
 paintBudget(metadata.budget);
 for(const text of ['Local CLIP fixed candidate 18/22 vs fully nested 15/22. Raw diagnostic coverage 100%; operational auto-coverage 0%. No 90% prospective accuracy claim.','Only three provisional good similarity groups; independence and pretraining overlap unknown.','Photo #14 is a duplicate used for repeatability, not scored twice. Photo #11 has a flagged source label.','Costs exclude unknown attempts when only a known subtotal is available; local hardware cost is unknown.',...summary.limitations])$('limitations').append(el('li',typeof text==='string'?text:JSON.stringify(text)));
 table();scatter();renderProviders();images();await refreshOwnedFeedback();}catch(err){showError('Evidence could not load: '+err.message);}})();
function renderFeedback(){
 const active=Boolean(feedbackState?.retained);
 $('retention-status').textContent='Annotation ID: '+feedbackId+' · '+(active?('Privately retained · revision '+feedbackState.revision+' · '+feedbackState.review_status+' · '+(feedbackState.training_eligible?'Owner approved; eligible for versioned export':'Not training eligible')):feedbackState?.revoked?'Consent withdrawn; image reference and labels deleted.':'No retained image / consent: training labeling disabled.');
 updateRunState();
}
async function changeFeedback(action,payload){
 if(feedbackBusy||uploadRunning||!feedbackState?.retained||!csrf)return;
 const annotationId=feedbackId,generation=selectionGeneration;
 feedbackBusy=true;renderFeedback();$('label-status').textContent='Saving…';
 try{
  await api('/api/feedback/'+annotationId+'/'+action,{method:'POST',headers:{'X-CSRF-Token':csrf,'Content-Type':'application/json'},body:JSON.stringify(payload)});
  // Verify the immutable write target, never a later selection.
  const state=await api('/api/feedback/'+annotationId);
  if(!selectionMatches(generation,annotationId))return;
  feedbackState=state;
  if(action==='revoke'){$('user-label').value='';$('label-note').value='';}
  await refreshOwnedFeedback(generation,annotationId);
  if(!selectionMatches(generation,annotationId))return;
  $('label-status').textContent=action==='revoke'?'Withdrawal verified. Prior exported copies require owner-managed removal.':'Saved and verified. Anonymous label is pending owner review; no model was updated.';
 }catch(err){
  if(!selectionMatches(generation,annotationId))return;
  $('label-status').textContent=err.message+' Refreshing exact annotation state…';
  try{const state=await api('/api/feedback/'+annotationId);if(!selectionMatches(generation,annotationId))return;feedbackState=state;$('user-label').value=state.label||'';$('label-note').value=state.note||'';}
  catch(refreshError){if(selectionMatches(generation,annotationId)){feedbackState=null;$('label-status').textContent='Could not verify annotation state. Controls disabled; contact the owner with annotation ID '+annotationId;}}
 }finally{feedbackBusy=false;renderFeedback();}
}
$('label-form').addEventListener('submit',event=>{event.preventDefault();changeFeedback('label',{label:$('user-label').value,note:$('label-note').value,expected_revision:feedbackState?.revision});});
$('revoke-retention').addEventListener('click',()=>changeFeedback('revoke',{}));

async function refreshOwnedFeedback(generation=selectionGeneration,annotationId=feedbackId){
 const response=await api('/api/feedback');if(!selectionMatches(generation,annotationId))return;const select=$('owned-feedback');clear(select);
 const blank=el('option','Select an earlier retained annotation…');blank.value='';select.append(blank);
 for(const row of response.annotations){const option=el('option',row.annotation_id+' · '+row.review_status+' · revision '+row.revision);option.value=row.annotation_id;select.append(option);}
 select.value=feedbackState?.retained?annotationId:'';updateRunState();
}
$('owned-feedback').addEventListener('change',async event=>{
 if(feedbackBusy||uploadRunning){event.target.value=feedbackState?.retained?feedbackId:'';return;}const key=event.target.value;if(!key)return;
 const generation=++selectionGeneration;feedbackId=key;feedbackState=null;feedbackBusy=true;renderFeedback();
 try{const state=await api('/api/feedback/'+key);if(!selectionMatches(generation,key))return;feedbackState=state;$('label-panel').hidden=false;$('user-label').value=state.label||'';$('label-note').value=state.note||'';$('label-status').textContent='Loaded your exact retained annotation. Earlier model results are not shown as the current upload.';}
 catch(err){if(selectionMatches(generation,key)){showError(err.message);feedbackState=null;}}
 finally{feedbackBusy=false;renderFeedback();}
});
