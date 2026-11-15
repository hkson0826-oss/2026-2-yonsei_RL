/* Local DOM functional checks; no browser navigation or network access. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { JSDOM, VirtualConsole } = require('jsdom');
const root = path.resolve(__dirname, '..');
const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', err => errors.push(err.message));
const html = fs.readFileSync(path.join(root,'output/role4/station_map.html'),'utf8');
const dom = new JSDOM(html,{runScripts:'dangerously',virtualConsole:vc});
const w=dom.window,d=w.document,$=id=>d.getElementById(id),checks=[];
function check(name,fn){fn();checks.push(name);}
function change(id,value){$(id).value=value;$(id).dispatchEvent(new w.Event('change'));}
function select(id){const node=[...d.querySelectorAll('.stop')].find(n=>n.getAttribute('aria-label').includes(id));assert.ok(node,`Stop ${id} visible`);node.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));}
check('initial reference renders 464 geographic markers',()=>assert.equal(d.querySelectorAll('.stop').length,464));
check('all reference coordinates and radii finite',()=>{for(const n of d.querySelectorAll('.stop'))for(const a of ['cx','cy','r'])assert.ok(Number.isFinite(Number(n.getAttribute(a))));});
check('missing-only filter renders 10 without inventing zero',()=>{change('scope','missing');assert.equal(d.querySelectorAll('.stop').length,10);select('112000440');assert.match($('detail').textContent,/미관측/);});
check('diagnostic subset labelled separately renders 259',()=>{change('scope','diagnostic');assert.equal(d.querySelectorAll('.stop').length,259);});
check('central-lane visibility policy preserves full source',()=>{change('scope','all');$('hideCentral').checked=true;$('hideCentral').dispatchEvent(new w.Event('change'));assert.equal(d.querySelectorAll('.stop').length,422);$('hideCentral').checked=false;$('hideCentral').dispatchEvent(new w.Event('change'));assert.equal(d.querySelectorAll('.stop').length,464);});
check('500m radius changes mapping count to 186',()=>{change('radius','500');assert.match($('radiusSummary').textContent,/186개 배정/);change('radius','300');assert.match($('radiusSummary').textContent,/103개 배정/);});
check('search matches station ID and selection populates monthly values',()=>{$('search').value='112000403';$('search').dispatchEvent(new w.Event('input'));assert.equal(d.querySelectorAll('.stop').length,1);select('112000403');assert.match($('detail').textContent,/23,966/);$('search').value='';$('search').dispatchEvent(new w.Event('input'));});
check('validation period keeps raw score above one',()=>{change('month','202609');select('112000403');assert.match($('detail').textContent,/1\.027/);change('month','train');});
check('same stop cannot become a valid 0m move',()=>{select('112900003');$('pickFrom').click();$('pickTo').click();assert.match($('pairResult').textContent,/재정차/);});
check('non-diagonal source 0m retained and warned',()=>{select('112900157');$('pickTo').click();assert.match($('pairResult').textContent,/0\.0m/);assert.match($('pairResult').textContent,/스냅 근사 경고/);});
check('unknown directed pair yields undefined reward',()=>{select('112000440');$('pickTo').click();assert.match($('pairResult').textContent,/보상을 정의할 수 없습니다/);});
check('candidate exclusion is distinguished from arithmetic',()=>{select('112000403');$('pickTo').click();assert.match($('pairResult').textContent,/유효 행동 판정이 아닙니다/);});
check('zoom and reset change and restore geographic viewport',()=>{const initial=$('map').getAttribute('viewBox');$('zoomIn').click();assert.notEqual($('map').getAttribute('viewBox'),initial);$('reset').click();assert.equal($('map').getAttribute('viewBox'),initial);});
const roadData=JSON.parse(fs.readFileSync(path.join(root,'data/routes/v1/routes.geojson'),'utf8'));
check('all24actual road options preserved without shrinking464universe',()=>{assert.equal(roadData.features.length,24);assert.equal($('roadExample').options.length,25);assert.equal(d.querySelectorAll('.stop').length,464);});
check('selectedroadline uses all original geometry vertices not a straight substitute',()=>{change('roadExample','112000031__112900230');const f=roadData.features.find(f=>f.properties.route_id==='112000031__112900230'),n=$('pairLayer').querySelector('polyline');assert.ok(n);assert.equal(n.getAttribute('data-route-id'),f.properties.route_id);assert.equal(n.getAttribute('points').trim().split(/\s+/).length,f.geometry.coordinates.length);assert.ok(f.geometry.coordinates.length>2);});
check('same-response routercostandduration distinguished fromlegacy cost',()=>{const t=$('pairResult').textContent;assert.match(t,/1,517\.8m/);assert.match(t,/118\.3초/);assert.match(t,/기존 부분 행렬/);assert.match(t,/자동차 프로파일 추천/);assert.match(t,/원시 성분/);assert.match(t,/미검증 선형 기준식/);assert.match(t,/실측/);});
check('reverse cachedroad has independently recorded metrics',()=>{change('roadExample','112900230__112000031');assert.match($('pairResult').textContent,/1,181\.5m/);assert.equal($('pairLayer').querySelector('polyline').getAttribute('data-route-id'),'112900230__112000031');});
check('allcachedroads overlay remains24independent paths',()=>{$('showRoadCache').checked=true;$('showRoadCache').dispatchEvent(new w.Event('change'));assert.equal($('roadOverviewLayer').querySelectorAll('polyline').length,24);});
check('profileweightnotelapsedtimecorrectlyshown',()=>{change('roadExample','112000073__112000125');assert.match($('pairResult').textContent,/routability/);assert.match($('pairResult').textContent,/108\.7/);assert.match($('pairResult').textContent,/88\.5초/);assert.match($('pairResult').textContent,/시간·거리 최소 보장 아님/);});
check('no map script runtime errors',()=>assert.deepEqual(errors,[]));
change('scope','all');change('radius','300');change('month','train');w.eval('selected=null;from=null;to=null;render();');
const evidence={method:'Node jsdom DOM simulation; no browser navigation, screenshots, network or layout certification',passed:checks.length,checks,errors,browser_visual_layout_verified:false,offline_data_rendered:true};
fs.writeFileSync(path.join(root,'docs/evidence/map_validation.json'),JSON.stringify(evidence,null,2)+'\n');
// Optional vector snapshot of the actual generated SVG for separate figure inspection.
const svg=$('map').cloneNode(true);svg.setAttribute('xmlns','http://www.w3.org/2000/svg');svg.setAttribute('width','960');svg.setAttribute('height','680');
fs.mkdirSync(path.join(root,'tmp'),{recursive:true});fs.writeFileSync(path.join(root,'tmp/role4_map_snapshot.svg'),new w.XMLSerializer().serializeToString(svg));
// A static figure of the actual24independentroadobservations, not a browser screenshot.
fs.writeFileSync(path.join(root,'tmp/role4_road_snapshot.svg'),new w.XMLSerializer().serializeToString(svg));
console.log(`${checks.length} map DOM checks passed (not a browser visual-layout test).`);
dom.window.close();
