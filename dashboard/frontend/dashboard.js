"use strict";
const $=id=>document.getElementById(id);let benchmarks=[],providers=[],cohortData=null,csrf='',previewURL='',imageReady=false,imageChecking=false,validationSerial=0,uploadRunning=false;
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
const pct=v=>v==null?'Not evaluated':(100*v).toFixed(1)+'%';const ratio=(n,d)=>n==null?'Not evaluated':n+'/'+d;
async function api(path,options){const response=await fetch(path,{credentials:'same-origin',cache:'no-store',...options});const body=await response.json();if(!response.ok)throw Error(body.error||'Request failed');return body;}
function clear(node){node.replaceChildren();}
function showError(message){$('global-error').hidden=false;$('global-error').textContent=message;}
function cost(m){const low=m.usd_per_submitted_image_low,high=m.usd_per_submitted_image_high;return low==null||high==null?'Not evaluated':('$'+low.toFixed(6)+(low===high?'':'–$'+high.toFixed(6)));}
function support(m){const p=providers.find(p=>p.id===m.provider_id);return p?(p.status==='available'?'Configured · '+(p.paid?'remote':'saved head'):'Unavailable'):'No configured adapter';}
function paintBudget(b){
 if(!b.live_snapshot){$('budget').textContent='Current private ledger unavailable. Remaining requests and invoice total cannot be verified. Providers fail closed; historical request counts are not a live budget. '+(b.note||'');return;}
 const planning=b.additional_planning_high_usd==null?'not measured':'$'+b.additional_planning_high_usd.toFixed(6);
 $('budget').textContent='LIVE READ-ONLY BUDGET · '+(b.used??'Not available')+'/'+b.lifetime_cap+' lifetime requests · '+(b.remaining??'Not available')+' remaining · '+(b.monetary_limit_removed?'Monetary cap removed (not unlimited requests)':('USD '+(b.additional_approved_usd??'not verified')+' additional approved'))+' · planning high '+planning+'. Exact invoice not available. '+(b.note||'');
}
async function refreshMetadata(generation=selectionGeneration){const metadata=await api('/api/methods');if(generation!==selectionGeneration)return;providers=metadata.methods;paintBudget(metadata.budget);renderProviders(true);if(cohortData)table();}
function filteredMethods(){
 const query=$('search').value.toLowerCase(),family=$('family').value,sort=$('sort').value;
 return benchmarks.filter(m=>(m.label+' '+m.method+' '+m.evaluation).toLowerCase().includes(query)&&(!family||m.family===family)).sort((a,b)=>{
  if(a.evaluated!==b.evaluated)return a.evaluated?-1:1;
  return sort==='method'?a.label.localeCompare(b.label):sort==='unsafe_good_of_bad'?(a[sort]??99)-(b[sort]??99):(b[sort]??-1)-(a[sort]??-1);
 });
}
function table(){
 const rows=filteredMethods();clear($('benchmark-rows'));$('visible-count').textContent=rows.length+' / '+benchmarks.length+' methods';
 for(const m of rows){
  const tr=el('tr'),td=el('td'),button=el('button',m.label,'source-button');tr.dataset.method=m.method;
  button.type='button';button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-label',m.label+' sources and scope');button.addEventListener('click',()=>showMethod(m));
  td.append(button,el('span',m.family,'tag'));tr.append(td);
  const latency=m.latency_seconds==null?m.latency_label:m.latency_seconds.toFixed(2)+' s';
  const values=[[pct(m.accuracy_binary),ratio(m.correct_binary,m.binary_n)],[pct(m.accepted_accuracy),m.evaluated?m.accepted_n+' binary outputs':'No full-cohort score'],
   [pct(m.binary_coverage),m.evaluated?m.accepted_n+'/'+m.binary_n+' · '+m.review_outputs+' review':'Not evaluated'],
   [ratio(m.unsafe_good_of_bad,m.bad_n),m.unsafe_good_of_bad?'bad → good':''],[latency,m.latency_n?m.latency_label+' · n='+m.latency_n:'Expand for scope'],
   [cost(m),m.hosting_usd_hour!=null?'+ $'+m.hosting_usd_hour.toFixed(2)+'/h hosting':m.cost_label],[support(m),'Independent of historical score']];
  for(let i=0;i<values.length;i++){const cell=el('td'),metric=el('div',values[i][0],'metric');metric.append(el('small',values[i][1]));if(i===3&&m.unsafe_good_of_bad)metric.classList.add('unsafe');cell.append(metric);tr.append(cell);}
  if(m.training_one_off_usd!=null)tr.children[6].append(el('small','$'+m.training_one_off_usd.toFixed(2)+' one-off training','subtle'));
  $('benchmark-rows').append(tr);
 }
 scatter();
}
function showMethod(m){
 $('method-title').textContent=m.label+' · sources and scope';const body=$('method-detail-body');clear(body);
 const facts=[['Evaluation',m.evaluation],['Prediction source',m.source],['Binary outputs',m.evaluated?m.accepted_n+'/'+m.binary_n+' · '+m.review_outputs+' reviews · '+m.errors+' errors':'Not evaluated'],
  ['Timing scope',m.latency_scope+(m.latency_n?' n='+m.latency_n+'.':'')],['Timing source',m.latency_source||'No cohort timing source recorded'],
  ['Timing date','Frozen archive baseline '+cohortData.provenance.archive_baseline+'. Per-case calendar dates are not recorded; no date inferred.'],
  ['Cost scope',m.cost_note],['Cost source',m.cost_source],['Retail snapshot',m.cost_snapshot],
  ['Source-review diagnostic',m.review_diagnostic],['Upload runtime',support(m)+'. '+(providers.find(p=>p.id===m.provider_id)?.reason||'No adapter for this benchmark method is configured. Historical evidence does not enable uploads.')]];
 if(m.smoke_seconds!=null)facts.splice(4,0,['Startup context',m.smoke_seconds.toFixed(2)+' s · n='+m.smoke_n+' synthetic Azure smoke; not cohort latency.']);
 const dl=el('dl');for(const [name,value]of facts)dl.append(el('dt',name),el('dd',value));body.append(dl);$('method-details').showModal();
}
$('close-method-details').addEventListener('click',()=>$('method-details').close());
function selectCohort(){
 const c=cohortData.cohorts[$('cohort').value];benchmarks=c.methods;
 $('cohort-n').textContent=c.n;$('cohort-population').textContent=c.bad+' provisional bad · '+c.good+' provisional good. '+(c.id==='shared9'?'Same nine photos for all six methods.':'GPT fine-tuned was not evaluated on all 22.');
 $('cohort-caption').textContent=c.caption;$('cohort-description').textContent=c.id==='shared9'?'Nine matched evaluation photos: 5 bad, 4 good. No source-review photos in this cohort.':'22 binary photos: 13 bad, 9 good. GPT has no full-22 score and is not ranked.';
 $('unsafe-heading').textContent='False good / '+c.bad;$('method-count').textContent=benchmarks.filter(m=>m.evaluated).length+' / '+benchmarks.length;
 $('cohort-card').textContent=c.caption;
 const best=benchmarks.find(m=>m.method==='clip'),overall=benchmarks.filter(m=>m.evaluated).sort((a,b)=>b.accuracy_binary-a.accuracy_binary)[0];
 $('best-local').textContent=ratio(best.correct_binary,best.binary_n);$('best-overall').textContent=ratio(overall.correct_binary,overall.binary_n);$('best-overall-label').textContent=overall.label+' · selected cohort only';
 table();
}
function scatter(){const svg=$('scatter'),ns='http://www.w3.org/2000/svg';clear(svg);const s=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;svg.append(n);return n;};
 for(let v=0;v<=100;v+=25){const x=48+v*5.5,y=247-v*2.05;s('line',{x1:48,y1:y,x2:598,y2:y,stroke:'#e4e9eb'});s('text',{x:38,y:y+4,'text-anchor':'end',fill:'#697a83','font-size':10},v+'%');s('text',{x,y:265,'text-anchor':'middle',fill:'#697a83','font-size':10},v+'%');}
 s('text',{x:320,y:286,'text-anchor':'middle',fill:'#697a83','font-size':10},'RAW BINARY COVERAGE →');s('text',{x:48,y:18,fill:'#697a83','font-size':10},'OVERALL ACCURACY');
 filteredMethods().forEach((m,i)=>{if(m.accuracy_binary==null||m.binary_coverage==null)return;const color=m.unsafe_good_of_bad?'#b94237':m.family==='custom-local'?'#287b78':'#596ea7';const n=s('circle',{cx:48+m.binary_coverage*550+(i%3-1)*3,cy:247-m.accuracy_binary*205+(i%2)*3,r:5,fill:color,opacity:.75,tabindex:0,role:'img','aria-label':m.method+': '+pct(m.accuracy_binary)+' overall; '+pct(m.binary_coverage)+' coverage; '+m.unsafe_good_of_bad+' false good / '+m.bad_n});const title=document.createElementNS(ns,'title');title.textContent=n.getAttribute('aria-label');n.append(title);});}
function renderProviders(preserve=false){const selected=new Set([...document.querySelectorAll('input[name=provider]:checked')].map(n=>n.value));clear($('provider-list'));for(const p of providers){const label=el('label',undefined,'provider'),input=el('input');input.type='checkbox';input.value=p.id;input.name='provider';input.disabled=p.status!=='available'||uploadRunning||feedbackBusy;input.checked=p.status==='available'&&(preserve?selected.has(p.id):!p.paid);const text=el('span');text.append(el('strong',p.label),el('small',p.status.toUpperCase()+(p.paid?' · PAID REMOTE':' · LOCAL')+' · '+(p.reason||'Configured adapter; explicit consent required for remote inference.')));label.append(input,text);$('provider-list').append(label);}updateRunState();}
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
for(const id of ['search','family','sort'])$(id).addEventListener('input',table);
$('cohort').addEventListener('change',selectCohort);$('inference-form').addEventListener('submit',upload);
(async()=>{try{
 const [summary,metadata,session]=await Promise.all([api('/api/benchmarks'),api('/api/methods'),api('/api/session')]);
 cohortData=summary;providers=metadata.methods;csrf=session.csrf_token;$('cohort').value=summary.default_cohort;$('evidence-source').textContent=summary.source;
 for(const f of [...new Set(summary.methods.map(m=>m.family))].sort()){const option=el('option',f);option.value=f;$('family').append(option);}
 paintBudget(metadata.budget);
 for(const text of summary.limitations)$('limitations').append(el('li',text));
 selectCohort();renderProviders();await refreshOwnedFeedback();
 }catch(err){showError('Evidence could not load: '+err.message);}})();
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
