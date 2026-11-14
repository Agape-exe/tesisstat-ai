const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {chromium} = require(process.env.QA_PLAYWRIGHT_PATH || 'C:/Users/Melissa/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root = process.cwd(), out = path.join(root, 'docs/uxui-final/evidencia');
const ids = JSON.parse(fs.readFileSync('.cache/uxui-final-qa/ids.json','utf8'));
const sections = [['documents','Documentos'],['methodology','Metodología'],['instrument','Instrumento'],['datasets','Datos'],['analysis','Análisis'],['results','Resultados'],['reports','Informes']];
const sizes = [[1440,900],[1366,768],[390,844]];
const executablePath = process.env.QA_CHROMIUM_PATH || 'C:/Users/Melissa/AppData/Local/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-win64/chrome-headless-shell.exe';
(async()=>{
 const browser = await chromium.launch({executablePath});
 const ctx = await browser.newContext({locale:'es-PE',deviceScaleFactor:1});
 const network=[],errors=[],blocked=[],geometry=[];
 await ctx.route('**/*', async route=>{const url=new URL(route.request().url());if(url.hostname==='127.0.0.1') return route.continue();blocked.push(url.origin);return route.abort();});
 ctx.on('request',r=>{if(r.url().includes('/api/'))network.push({method:r.method(),url:r.url()});});
 ctx.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));
 const real=await ctx.newPage(),ref=await ctx.newPage();
 async function open(p,section,project=ids.populated,port=5179,view=''){
  await p.goto(`http://127.0.0.1:${port}/#project=${project}&section=${section}${view?'&view='+view:''}`);await p.reload();
  await p.waitForLoadState('networkidle');
  if(section==='documents')await p.getByText('sintetico.docx',{exact:true}).waitFor({state:'visible'});
  if(section==='methodology')await p.getByRole('button',{name:'Editar metodología',exact:true}).waitFor({state:'visible'});
  if(section==='datasets')await p.getByRole('table').waitFor({state:'visible'});
  if(section==='analysis')await p.getByRole('button',{name:view==='plan'?'Nueva propuesta':'Editar vinculaciones',exact:true}).waitFor({state:'visible'});
  if(section==='results') {await p.getByRole('region',{name:'Resultado estadístico',exact:true}).waitFor({state:'visible'});const show=p.getByRole('button',{name:'Mostrar pares autorizados',exact:true});if(await show.count())await show.click();await p.locator('.authorized-scatter svg').waitFor({state:'visible'});}
  if(section==='reports')await p.getByRole('heading',{name:'Exportaciones',exact:true}).waitFor({state:'visible'});
  await p.evaluate(() => window.scrollTo(0,0));await p.waitForTimeout(100);
 }
 for(const [w,h] of sizes){
  await real.setViewportSize({width:w,height:h});await ref.setViewportSize({width:w,height:h});
  for(const [s,label] of sections){
   const view=s==='analysis'?'plan':'';
   await open(real,s,ids.populated,5179,view);
   const refSection=s==='datasets'?'data':s;
   await ref.goto(`http://127.0.0.1:8020/TesisStat_AI_Mockup_Integral_Corregido.html#proyecto=p1&vista=${refSection}`);await ref.reload();await ref.waitForLoadState('networkidle');
   await real.evaluate(() => window.scrollTo(0,0));
   await real.screenshot({path:path.join(out,`react-${s}-${w}.png`)});await ref.screenshot({path:path.join(out,`mockup-${s}-${w}.png`)});
   if(w===390 || w===1440)await real.screenshot({path:path.join(out,`react-${s}-${w}-completa.png`),fullPage:true});
   const g=await real.evaluate(()=>{const box=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};};return {viewport:[innerWidth,innerHeight],documentWidth:document.documentElement.scrollWidth,header:box('.rp-section-header'),content:box('.rp-section-columns'),support:box('.rp-support')};});
   if(g.documentWidth>w)throw Error(`Horizontal overflow ${s}/${w}: ${g.documentWidth}`);
   const reference=await ref.evaluate(()=>{const q=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}};return {header:q('.detail-head'),content:q('.two-columns'),titleFont:getComputedStyle(document.querySelector('h1')).fontSize};});
   geometry.push({section:s,...g,reference});
  }
  // Same database, same viewport, same UI state on backup and current source.
  for(const section of ['listing','assistant']){
   const suffix=section==='listing'?'':`#project=${ids.empty}&section=assistant`;
   for(const [p,port,prefix] of [[ref,5180,'respaldo'],[real,5179,'actual']]){
    await p.goto(`http://127.0.0.1:${port}/${suffix}`);await p.reload();await p.waitForLoadState('networkidle');
    await p.getByRole('heading',{name:section==='listing'?'Mis investigaciones':'Asistente IA',exact:true}).waitFor();
    await p.mouse.move(0,0);await p.waitForTimeout(400);await p.screenshot({path:path.join(out,`${prefix}-${section}-${w}.png`)});
   }
  }
 }
 fs.writeFileSync('docs/uxui-final/geometria.json',JSON.stringify(geometry,null,2));
 fs.writeFileSync('docs/uxui-final/red-capturas.json',JSON.stringify({errors,blocked,requests:network},null,2));
 if(errors.length||blocked.length)throw Error(JSON.stringify({errors,blocked}));
 // Compare images via canvas, retaining each source at its original dimensions.
 const compose=await ctx.newPage(),pixelChecks=[];
 for(const [w,h] of sizes){
  for(const [s] of sections){
   await compose.setViewportSize({width:w*2,height:h+36});
   await compose.setContent(`<style>*{box-sizing:border-box}body{margin:0;background:#f2f0fe;font:12px system-ui;color:#211c48}.pair{display:grid;grid-template-columns:${w}px ${w}px}header{height:36px;padding:10px 14px}img{display:block;width:${w}px;height:${h}px}</style><div class="pair"><div><header>MOCKUP APROBADO</header><img src="http://127.0.0.1:8021/docs/uxui-final/evidencia/mockup-${s}-${w}.png"></div><div><header>REACT + FASTAPI · DATOS SINTÉTICOS</header><img src="http://127.0.0.1:8021/docs/uxui-final/evidencia/react-${s}-${w}.png"></div></div>`);
   await compose.locator('img').evaluateAll(imgs=>Promise.all(imgs.map(i=>i.decode())));
   await compose.screenshot({path:path.join(out,`comparacion-${s}-${w}.png`)});
  }
  for(const s of ['listing','assistant']){
   await compose.goto('http://127.0.0.1:8021/');
   const difference=await compose.evaluate(async ({s,w})=>{const data=[];for(const prefix of ['respaldo','actual']){const i=new Image();i.src=`/docs/uxui-final/evidencia/${prefix}-${s}-${w}.png`;await i.decode();const c=document.createElement('canvas');c.width=i.width;c.height=i.height;c.getContext('2d').drawImage(i,0,0);data.push(c.getContext('2d').getImageData(0,0,i.width,i.height).data);}let pixels=0,maxDelta=0;for(let n=0;n<data[0].length;n+=4){if(data[0][n]!==data[1][n]||data[0][n+1]!==data[1][n+1]||data[0][n+2]!==data[1][n+2])pixels++;maxDelta=Math.max(maxDelta,Math.abs(data[0][n]-data[1][n]),Math.abs(data[0][n+1]-data[1][n+1]),Math.abs(data[0][n+2]-data[1][n+2]));}return {pixels,maxDelta};},{s,w});
   pixelChecks.push({section:s,width:w,height:h,changedPixels:difference.pixels,maxChannelDelta:difference.maxDelta});
  }
 }
 fs.writeFileSync('docs/uxui-final/preservacion-aprobadas.json',JSON.stringify(pixelChecks,null,2));
 const manifest=fs.readdirSync(out).filter(f=>f.endsWith('.png')).map(file=>{const b=fs.readFileSync(path.join(out,file));return {file,bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex')};});fs.writeFileSync('docs/uxui-final/capturas-manifest.json',JSON.stringify(manifest,null,2));
 console.log(JSON.stringify({comparisons:21,viewports:3,errors,blocked,pixelChecks}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
