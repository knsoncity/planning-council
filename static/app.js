'use strict';
const $ = id => document.getElementById(id);
const state = {token:'', meetings:[], id:null, meeting:null, selected:null, selectedMember:null, follow:true, cursor:0, streams:{}, parent:null, busy:false, polling:false, previous:null, signature:null};
const labels = {draft:'초안',running:'진행 중',stopping:'중단 확인 중',completed:'완료',failed:'실행 실패',cancelled:'중단됨',interrupted:'앱 종료로 중단'};
const phases = {review:'독립 검토',internal:'토론 1 · 팀 내 반박',debate:'토론 2 · 팀 간 토론',decision:'최종 · CBO 판단'};
const isLite=()=>state.meeting?.protocol==='lite-v1';
const isMembers=()=>['members-v2','lite-v1'].includes(state.meeting?.protocol);
const totalCalls=()=>state.meeting?.protocol==='members-v2'?61:9;
function phaseLabel(phase){if(isLite()&&phase==='debate')return '대표 교차 토론';return !isMembers()&&phase==='review'?'1라운드 · 팀 검토·내부 반론':phases[phase]||phase;}
function memberLabel(id){const m=(state.meeting?.roster||[]).find(x=>x.id===id);return m?`${m.team} · ${m.role}`:id;}
function speaker(run){return run.team==='CBO'?'CBO':run.member_id?memberLabel(run.member_id)===run.member_id?`${run.team} · ${run.member_role||run.member_id}`:memberLabel(run.member_id):run.team+'팀';}
function el(tag, text, cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function notice(message){$('notice').textContent=message||'';$('notice').hidden=!message;}
async function api(path, data){const options=data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Council-Token':state.token},body:JSON.stringify(data)};const r=await fetch(path,options);const value=await r.json();if(!r.ok)throw new Error(value.error||'요청 실패');return value;}
function date(s){return new Date(s).toLocaleString('ko-KR',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});}
function listSection(title, items){const box=el('div',undefined,'speech-section');box.append(el('h3',title));const ul=el('ul');for(const item of items||[])ul.append(el('li',item));if(!items?.length)box.append(el('p','명시된 항목 없음','muted'));else box.append(ul);return box;}
function renderVerdictHeading(position,summary){
 const split=position.indexOf(':');
 const short=split>0&&split<=28;
 $('verdict-title').textContent=short?position.slice(0,split).trim():'CBO 결론';
 $('verdict-position').textContent=short?position.slice(split+1).trim():position;
 $('verdict-position').hidden=!$('verdict-position').textContent;
 $('verdict-summary').textContent=summary;
}
function renderVerdict(r){
 const box=$('verdict-body');box.replaceChildren();
 const teamFormat=['종합','사업','기획','개발','디자인'].every((name,i)=>r.perspectives[i]?.role===name);
 const views=el('section',undefined,'verdict-views');
 views.append(el('h3',teamFormat?'팀별 판단 · 역할 · 시작 조건':'CBO가 살펴본 관점'));
 if(!teamFormat)views.append(el('p','이전 형식의 원문입니다. 팀별 역할과 업무 순서를 포함한 결론은 새 회의부터 작성됩니다.','muted'));
 for(const v of r.perspectives){const row=el('div',undefined,'view-row');row.append(el('b',v.role),el('span',v.view.replaceAll(' / ','\n')));views.append(row);}
 const steps=el('section',undefined,'speech-section verdict-steps');steps.append(el('h3',teamFormat?'누가 먼저 무엇을 할까요?':'CBO가 제안한 다음 행동'));
 const list=el(teamFormat?'ol':'ul');
 for(const item of r.next_steps||[])list.append(el('li',item.replaceAll(' | ','\n')));
 steps.append(list);
 let debate; if(r.challenges?.length){debate=el('details',undefined,'verdict-views speech-section');debate.append(el('summary','어떤 의견이 부딪혔나요? · 논쟁과 CBO 설명'));for(const c of r.challenges){const row=el('div',undefined,'challenge');row.append(el('b',memberLabel(c.target)),el('p','상대의 생각 · '+c.claim),el('p','CBO의 설명 · '+c.response));debate.append(row);}}
 box.append(views,steps,listSection('주의할 점 · 멈춰야 할 조건',r.risks),listSection('아직 의견이 다른 부분',r.dissent));if(debate)box.append(debate);
}
function renderList(){const list=$('meeting-list');list.replaceChildren();for(const m of state.meetings){const b=el('button',undefined,'meeting-item'+(m.id===state.id?' selected':''));b.append(el('strong',m.title),el('small',`${m.protocol==='lite-v1'?'간단 · ':m.protocol==='members-v2'?'전체 · ':''}v${m.version} · ${labels[m.status]} · ${date(m.created)}`));b.onclick=()=>select(m.id);list.append(b);}if(!state.meetings.length)list.append(el('p','아직 회의가 없습니다.','muted'));}
async function select(id){state.id=id;state.selected=null;state.selectedMember=null;state.follow=true;state.cursor=0;state.streams={};state.previous=null;state.signature=null;localStorage.setItem('council:selected',id);const url=new URL(location.href);url.searchParams.set('meeting',id);history.replaceState(null,'',url);await refresh();}
async function refresh(){if(state.polling)return;state.polling=true;try{state.meetings=await api('/api/meetings');renderList();if(!state.id)return;const id=state.id;const [m,events]=await Promise.all([api('/api/meetings/'+id),api('/api/events/'+id+'?after='+state.cursor)]);if(id!==state.id)return;state.meeting=m;for(const e of events){state.cursor=Math.max(state.cursor,e.id);if(e.kind==='delta')state.streams[e.run]=(state.streams[e.run]||'')+e.payload.text;if(e.kind==='response')state.streams[e.run]=e.payload.text;}
if(m.parent&&!state.previous)state.previous=await api('/api/meetings/'+m.parent);const signature=JSON.stringify(m);const selectedRunning=m.runs.find(r=>r.id===state.selected)?.status==='running';if(signature!==state.signature||selectedRunning){renderMeeting();state.signature=signature;}$('save-state').textContent='내 컴퓨터에 저장됨';}catch(e){notice('연결을 확인해 주세요. '+e.message);$('save-state').textContent='연결 끊김';}finally{state.polling=false;}}
function latest(team){return [...state.meeting.runs].reverse().find(r=>r.team===team);}
function renderMeeting(){const m=state.meeting;$('empty').hidden=true;$('workspace').hidden=false;$('export').disabled=false;$('meeting-title').textContent=m.title;$('meeting-meta').textContent=`COUNCIL / ${isLite()?'간단 · 9회':isMembers()?'전체 · 61회':'이전 방식 · 9회'} / v${m.version} / ${date(m.created)}`;$('meeting-status').textContent=labels[m.status];$('meeting-status').className='pill'+(['failed','interrupted'].includes(m.status)?' error':'');const running=['running','stopping'].includes(m.status);$('stop').hidden=!running;$('stop').disabled=m.status==='stopping';$('resume').hidden=!['failed','cancelled','interrupted','draft'].includes(m.status);$('resume').textContent=m.status==='draft'?'회의 시작':'미완료 단계 재시도';$('revise').disabled=running;
$('brief-text').textContent=m.brief;$('brief-version').textContent=`v${m.version} · 근거 ${m.evidence.length}개 · 실행 중 고정`;$('skill-hash').textContent=`planning-council 지침 스냅샷 · ${m.skill_hash.slice(0,12)}`;const evidence=$('evidence-list');evidence.replaceChildren();for(const e of m.evidence){const row=el('div',undefined,'evidence');row.append(el('b',e.id),el('span',e.text));evidence.append(row);}if(!m.evidence.length)evidence.append(el('p','등록된 근거가 없습니다. 확정적 판단 대신 가정과 검증 과제를 도출합니다.','muted'));
const active=m.runs.find(r=>r.status==='running');const complete=new Set(m.runs.filter(r=>r.status==='completed').map(r=>r.step));$('complete-count').textContent=complete.size;renderNowSpeaking(active,complete.size);$('total-count').textContent=String(totalCalls());$('live-state').textContent=active?'● 실제 모델 응답 수신 중':labels[m.status];$('table-label').textContent=active?`${speaker(active)} 검토 중`:m.status==='completed'?'검토와 판단을 마쳤습니다':isMembers()?`하나의 안건, ${isLite()?4:20}명의 독립 의견`:'하나의 안건, 다섯 가지 책임';$('table-subtitle').textContent=active?`${active.provider==='codex'?'Codex':'Claude'} · ${phaseLabel(active.phase)}`:m.status==='failed'?'실패한 단계의 기록을 확인해 주세요':'실행 기록에서 발언을 선택할 수 있습니다';
document.querySelectorAll('[data-phase]').forEach(n=>n.classList.toggle('active',n.dataset.phase===(active?.phase||(m.status==='completed'?'decision':m.runs.at(-1)?.phase))));
if(state.follow){state.selected=active?.id||m.runs.at(-1)?.id||null;state.selectedMember=m.runs.find(r=>r.id===state.selected)?.member_id||null;}else if(!state.selected&&state.selectedMember){state.selected=[...m.runs].reverse().find(r=>r.member_id===state.selectedMember)?.id||null;}
renderSeats(active);
renderSpeech(m.runs.find(r=>r.id===state.selected));renderTimeline();renderChanges();const cbo=[...m.runs].reverse().find(r=>r.team==='CBO'&&r.status==='completed');$('verdict-section').hidden=!cbo;if(cbo){const guide=m.reading_guide;
const verdict=guide?.result||cbo.result;renderVerdictHeading(verdict.position,verdict.summary);
const explanation=$('verdict-explanation');explanation.replaceChildren();explanation.hidden=!guide;
renderVerdict(guide?.result||cbo.result);
if(guide){const note=el('p','쉬운 설명 · 기존 토론을 바탕으로 별도 작성한 해설입니다. 업무 순서는 추가 제안이며, 원래 CBO 발언과 팀의 합의를 대체하지 않습니다.','muted');const original=el('button','원래 CBO 발언 확인','quiet');original.onclick=()=>{state.selected=cbo.id;state.selectedMember=cbo.member_id;state.follow=false;renderMeeting();$('speaker-title').scrollIntoView({behavior:'smooth',block:'center'});};explanation.append(note,original);}}}
function renderNowSpeaking(active,count){
const m=state.meeting,total=totalCalls();
$('now-speaking').classList.toggle('live',!!active);
$('now-name').textContent=active?speaker(active):m.status==='completed'?'CBO 판단까지 완료':labels[m.status]||'회의 대기';
$('now-phase').textContent=active?`${active.provider==='codex'?'Codex':'Claude'} · 실제 응답 생성 중`:m.status==='completed'?'구성원을 선택해 의견과 반박을 확인하세요':m.title;
$('now-stage').textContent=active?phaseLabel(active.phase):labels[m.status];$('now-count').textContent=`${count} / ${total} 실행`;
$('meeting-progress').max=total;$('meeting-progress').value=count;
$('now-follow').textContent=m.status==='completed'?'CBO 결론 보기':'현재 발언 보기';
}
function renderSeats(active){
const m=state.meeting, layout=$('table-layout'), table=layout.querySelector('.round-table');layout.replaceChildren();
const selected=m.runs.find(r=>r.id===state.selected);
const teams=['기획','사업','디자인','개발'];
function choose(r){if(r){state.selected=r.id;state.selectedMember=r.member_id||null;state.follow=false;renderMeeting();}}
for(const [index,team] of teams.entries()){
 if(index===2)layout.append(table);
 const members=(m.roster||[]).filter(x=>x.team===team);
 if(isMembers()){
  const group=el('section',undefined,'team-group');group.setAttribute('aria-label',team+'팀 구성원');
  const head=el('div',undefined,'team-header');head.append(el('strong',team+'팀'),el('small',isLite()?'대표 1명 · 독립 실행':'5명 · 독립 실행'));group.append(head);
  const seats=el('div',undefined,'member-seats');
  for(const person of members){
   const r=[...m.runs].reverse().find(x=>x.member_id===person.id);
   const b=el('button',undefined,'member-seat');b.dataset.member=person.id;b.classList.toggle('running',active?.member_id===person.id);b.classList.toggle('chosen',(selected?.member_id||state.selectedMember)===person.id);b.classList.toggle('failed',r?.status==='failed');b.classList.toggle('rebuttal-target',!!selected?.result?.challenges?.some(c=>c.target===person.id));b.setAttribute('aria-pressed',String((selected?.member_id||state.selectedMember)===person.id));
   b.append(el('span',person.role.slice(0,1),'member-avatar'),el('span',person.role,'member-name'),el('small',person.provider==='codex'?'Codex':'Claude'),el('span',r?`${phaseLabel(r.phase)} · ${labels[r.status]||r.status}`:'독립 검토 대기','member-state'));
   b.onclick=()=>{state.follow=false;state.selectedMember=person.id;state.selected=r?.id||null;renderMeeting();};
   seats.append(b);
  }
  group.append(seats);layout.append(group);
 }else{
  const r=latest(team),b=el('button',undefined,'team-seat');b.dataset.team=team;b.classList.toggle('running',r?.status==='running');b.classList.toggle('chosen',r?.id===state.selected);b.append(el('strong',team+'팀'),el('small','이전 방식 · 5개 관점 통합'),el('span',r?`${phaseLabel(r.phase)} · ${labels[r.status]||r.status}`:'대기','team-state'));b.onclick=()=>choose(r);layout.append(b);
 }
}
const cbo=latest('CBO'),b=el('button',undefined,'team-seat cbo');b.dataset.team='CBO';b.classList.toggle('running',cbo?.status==='running');b.classList.toggle('chosen',cbo?.id===state.selected);b.append(el('strong','CBO · 최종 판단'),el('span',cbo?`${labels[cbo.status]||cbo.status} · Codex`:'모든 구성원의 검토·반박 후 판단','team-state'));b.onclick=()=>choose(cbo);layout.append(b);
$('execution-note').textContent=isLite()?'팀 대표 4명 독립 검토 → 교차 토론 1회 → CBO 판단. 총 9회 호출합니다. 20명 전체 검토와 팀 내부 토론은 생략합니다. 실제 토큰 사용량은 안건·자료·응답 길이에 따라 달라집니다.':isMembers()?'20명 독립 검토 → 팀 내 반박 → 팀 간 토론(최대 2라운드) → CBO 판단. 총 61회 별도 호출을 순차 실행합니다. 기존 9회 방식보다 시간·사용량이 늘어납니다. 각 자리를 클릭하면 실제 발언과 변경 기록을 볼 수 있습니다.':'이전 회의 기록: 팀별 5개 관점을 한 호출에서 검토한 9회 실행 방식입니다. 독립 구성원 방식은 새 회의부터 적용됩니다.';
document.querySelector('[data-phase="internal"]').hidden=!isMembers()||isLite();document.querySelector('[data-phase="review"]').textContent=isMembers()?'01 · 독립 검토':'01 · 팀 검토·내부 반론';document.querySelector('[data-phase="debate"]').textContent=isLite()?'02 · 대표 교차 토론':isMembers()?'03 · 팀 간 토론':'02 · 교차 토론';document.querySelector('[data-phase="decision"]').textContent=isLite()?'03 · CBO 판단':isMembers()?'04 · CBO 판단':'03 · CBO 판단';
}
function renderSpeech(run){const box=$('speech');const old=box.querySelector('details')?.open;box.replaceChildren();if(!run){$('speaker-title').textContent=state.selectedMember?memberLabel(state.selectedMember):'발언과 근거';box.append(el('p',state.selectedMember?'이 구성원은 아직 발언하지 않았습니다. 독립 검토가 끝나면 본인의 의견이 표시됩니다.':'회의를 시작하면 실제 검토 결과가 여기에 도착합니다.','waiting'));return;}$('speaker-title').textContent=speaker(run);const meta=el('div',undefined,'speech-meta');meta.append(el('span',run.provider==='codex'?'Codex':'Claude','pill'),el('span',phaseLabel(run.phase),'pill'),el('span',`시도 ${run.attempt} · ${labels[run.status]||run.status}`,'muted'));box.append(meta);if(isMembers()){const history=el('div',undefined,'member-history');history.append(el('small','이 구성원의 발언 이력'));for(const r of state.meeting.runs.filter(x=>run.member_id?x.member_id===run.member_id:x.team===run.team)){const b=el('button',`${phaseLabel(r.phase)} · ${labels[r.status]||r.status}`,r.id===run.id?'selected':'');b.onclick=()=>{state.selected=r.id;state.selectedMember=r.member_id||null;state.follow=false;renderMeeting();};history.append(b);}box.append(history);}
if(run.status==='running'){const waiting=el('div',undefined,'waiting');waiting.append(el('strong','실제 모델이 응답을 생성하고 있습니다.'),el('span','확인된 발언은 완료 후 근거와 함께 표시합니다.'));box.append(waiting);if(state.streams[run.id]){const d=el('details');d.open=old||false;d.append(el('summary','수신 중인 원본 응답 보기'),el('pre',state.streams[run.id],'stream'));box.append(d);}return;}
if(run.error){box.append(el('p',run.error,'prewrap'));box.append(el('p','기존 완료 발언은 보존됩니다. 미완료 단계만 재시도할 수 있습니다.','muted'));return;}
const r=run.result;if(!r)return;box.append(el('span',r.position,'pill position'),el('p',r.summary,'speech-summary'));const views=el('div',undefined,'speech-section');views.append(el('h3',isMembers()&&run.team!=='CBO'?'이 구성원의 독립 의견':'판단을 나누어 살펴보기'));for(const v of r.perspectives){const row=el('div',undefined,'view-row');row.append(el('b',v.role),el('span',v.view));views.append(row);}box.append(views);
if(r.challenges.length){const section=el('div',undefined,'speech-section');section.append(el('h3',isMembers()?'다른 의견에 대한 답변':'반론과 응답'));for(const c of r.challenges){const row=el('div',undefined,'challenge');row.append(el('b',memberLabel(c.target)),el('p','상대의 생각 · '+c.claim),el('p','내 생각과 이유 · '+c.response));
const peerPhase=run.phase==='internal'?'review':run.phase==='debate'?(isLite()?'review':'internal'):null;
const peers=state.meeting.runs.filter(x=>x.member_id===c.target&&x.status==='completed'&&(!peerPhase||x.phase===peerPhase)&&x.started<run.started);
if(isMembers()&&peers.length){const original=el('details');original.append(el('summary','상대가 실제로 작성한 원문 대조'));for(const peer of peers){original.append(el('h3',phaseLabel(peer.phase)),el('p',peer.result.summary));for(const view of peer.result.perspectives)original.append(el('p',view.view));}row.append(original);}
section.append(row);}box.append(section);}
const source=el('div',undefined,'speech-section');source.append(el('h3','판단에 사용한 근거'));for(const id of r.evidence_ids){const e=state.meeting.evidence.find(x=>x.id===id);source.append(el('p',`${id} · ${e?.text||'등록되지 않은 근거'}`,'prewrap'));}if(!r.evidence_ids.length)source.append(el('p','인용한 등록 근거 없음 · 주장과 제안의 검증이 필요합니다.','muted'));box.append(source,listSection('주의할 점',r.risks),listSection('다음 행동',r.next_steps),listSection('아직 의견이 다른 부분',r.dissent));
if(r.changes?.length){const changes=el('div',undefined,'speech-section');changes.append(el('h3','이 구성원의 판단 변경'));for(const c of r.changes){const row=el('div',undefined,'change-item');row.append(el('p','이전 · '+c.before,'before'),el('p','변경 · '+c.after),el('p','이유 · '+c.reason),el('small','근거: '+(c.evidence_ids.join(', ')||'별도 등록 근거 없음')));changes.append(row);}box.append(changes);}
const details=el('details',undefined,'speech-section');details.append(el('summary','원본 구조화 응답 · 사용량'),el('pre',JSON.stringify({response:r,usage:run.usage},null,2),'stream'),el('p','보고된 비용은 실제 청구액이 아닙니다. 사용량이 없으면 미확인입니다.','muted'));box.append(details);}
function renderTimeline(){const box=$('timeline');box.replaceChildren();for(const r of state.meeting.runs){const b=el('button',undefined,'timeline-item'+(r.id===state.selected?' chosen':''));const left=el('span');left.append(el('strong',speaker(r)),el('small',` · ${phaseLabel(r.phase)} · ${r.provider}`));b.append(left,el('small',`${labels[r.status]||r.status} · 시도 ${r.attempt}`));b.onclick=()=>{state.selected=r.id;state.selectedMember=r.member_id||null;state.follow=false;renderMeeting();$('speaker-title').scrollIntoView({behavior:'smooth',block:'center'});};box.append(b);}if(!state.meeting.runs.length)box.append(el('p','아직 실행 기록이 없습니다.','muted'));}
function renderChanges(){const box=$('changes');box.replaceChildren();if(state.previous){const prev=state.previous;const section=el('div',undefined,'change-item');section.append(el('b',`안건 v${prev.version} → v${state.meeting.version}`));const d=el('details');d.append(el('summary','이전 안건·자료와 비교'));for(const [label,a,b] of [['안건',prev.title,state.meeting.title],['목표·조건',prev.brief,state.meeting.brief],['근거',prev.evidence.map(x=>x.text).join('\n'),state.meeting.evidence.map(x=>x.text).join('\n')]]){d.append(el('h3',label+(a===b?' · 유지':' · 변경')),el('p','이전: '+a,'before'),el('p','현재: '+b));}const back=el('button','이전 회의 열기','quiet');back.onclick=()=>select(prev.id);section.append(d,back);box.append(section);}
let count=0;for(const run of state.meeting.runs){for(const c of run.result?.changes||[]){count++;const row=el('div',undefined,'change-item');row.append(el('b',`${speaker(run)} · ${phaseLabel(run.phase)}`),el('p','이전 · '+c.before,'before'),el('p','변경 · '+c.after),el('p','이유 · '+c.reason),el('small','근거: '+(c.evidence_ids.join(', ')||'별도 등록 근거 없음')));box.append(row);}}if(!count)box.append(el('p','모델이 명시한 판단 변경은 아직 없습니다. 변경이 없으면 이력을 만들어내지 않습니다.','muted'));}
function updateModeDescription(){$('mode-description').textContent=$('mode-input').value==='lite-v1'?'빠른 방향 검토용. 대표 4명 독립 검토 + 교차 토론 4회 + CBO 1회. 전체 대비 호출 수 약 85% 감소이며 토큰 절감률을 보장하지 않습니다.':'중요한 의사결정용. 20명 독립 검토 + 팀 내부 반박 20회 + 교차 토론 20회 + CBO 1회. 더 넓은 관점 검토에 시간과 사용량을 씁니다.';}
$('mode-input').onchange=updateModeDescription;
function openForm(revise=false){$('mode-input').value=revise&&state.meeting.protocol==='members-v2'?'members-v2':'lite-v1';updateModeDescription();$('form-error').textContent='';state.parent=revise?state.id:null;$('form-title').textContent=revise?'기존 안건을 새 버전으로 검토합니다':'어떤 결정을 함께 검토할까요?';$('title-input').value=revise?state.meeting.title:'';$('brief-input').value=revise?state.meeting.brief:'';$('evidence-input').value=revise?state.meeting.evidence.map(e=>e.text).join('\n'):'';$('meeting-dialog').showModal();}
async function submit(start){if(state.busy)return;if(!$('meeting-form').reportValidity())return;state.busy=true;$('submit-meeting').disabled=true;$('save-draft').disabled=true;try{const r=await api('/api/meetings',{title:$('title-input').value,brief:$('brief-input').value,evidence:$('evidence-input').value,parent:state.parent,protocol:$('mode-input').value});$('meeting-dialog').close();await select(r.id);if(start){await api('/api/meetings/'+r.id+'/start',{});await refresh();}notice('');}catch(e){$('form-error').textContent=e.message;notice(e.message);}finally{state.busy=false;$('submit-meeting').disabled=false;$('save-draft').disabled=false;}}
$('now-follow').onclick=()=>{if(!state.meeting)return;state.follow=true;renderMeeting();(state.meeting.status==='completed'?$('verdict-section'):$('speaker-title')).scrollIntoView({behavior:'smooth',block:'center'});};
$('new-meeting').onclick=()=>openForm();$('first-meeting').onclick=()=>openForm();$('revise').onclick=()=>openForm(true);$('close-dialog').onclick=()=>$('meeting-dialog').close();$('meeting-form').onsubmit=e=>{e.preventDefault();submit(true);};$('save-draft').onclick=()=>submit(false);$('follow').onclick=()=>{state.follow=true;renderMeeting();};
$('stop').onclick=async()=>{try{await api('/api/meetings/'+state.id+'/stop',{});await refresh();}catch(e){notice(e.message);}};
$('resume').onclick=async()=>{try{await api('/api/meetings/'+state.id+'/start',{});notice('');await refresh();}catch(e){notice(e.message);}};
$('export').onclick=async()=>{try{const data=await api('/api/meetings/'+state.id+'/export');const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`council-v${data.version}-${data.id.slice(0,8)}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}catch(e){notice(e.message);}};
async function init(){try{const boot=await api('/api/bootstrap');state.token=boot.token;$('connections').textContent=`Codex ${boot.providers.codex?'설치됨':'미설치'} · Claude ${boot.providers.claude?'설치됨':'미설치'}`;if(!boot.skill_available)notice('planning-council 스킬을 찾을 수 없습니다.');state.meetings=await api('/api/meetings');const requested=new URLSearchParams(location.search).get('meeting');const saved=state.meetings.some(m=>m.id===requested)?requested:localStorage.getItem('council:selected');state.id=state.meetings.find(m=>m.id===saved)?.id||state.meetings[0]?.id||null;await refresh();setInterval(refresh,1400);}catch(e){notice(e.message);}}
init();
