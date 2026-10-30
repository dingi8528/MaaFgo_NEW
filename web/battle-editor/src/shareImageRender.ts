import {apiPNG} from './api';
import type {Catalog,Json} from './model';
import type {CardPreviewConfig} from './npCardRequest';
import {SHARE_IMAGE_MAX_HEIGHT,SHARE_IMAGE_MAX_PIXELS,SHARE_IMAGE_WIDTH,shareImageModel} from './shareImageModel';
import type {ShareAction,ShareAttack,ShareEquip,ShareImageModel,ShareMember,SharePerson,ShareSkill} from './shareImageModel';

export interface ShareImageMatrix {matrix:string[];text?:string}
export interface EncodedShareImage {schema:1;format:'maafgo-share-image';digest?:string;anchor:ShareImageMatrix;markers:(ShareImageMatrix&{index:number;total:number})[]}
export interface ShareImageOptions {data:Json;catalog:Catalog;encoded:EncodedShareImage;region?:string;cardPreviewConfig?:CardPreviewConfig;signal?:AbortSignal;validation?:Json;costLimit?:number}
export interface RenderedShareImage {blob:Blob;width:number;height:number;warnings:string[]}
const W=SHARE_IMAGE_WIDTH,PAD=40,CONTENT=W-PAD*2,QR_PIXEL=5;
const BRAND_HEIGHT=168,BRAND_GAP=20;
const BRAND_ICON=new URL('../../../assets/resource/icon.png',import.meta.url).href;
const PROJECT_URL='https://github.com/xlxyvergil/MaaFgo';
const COLOR={background:'#edf4f8',paper:'#ffffff',ink:'#102e43',muted:'#5e7b8f',line:'#c5d8e5',blue:'#146b91',deep:'#124b6b',gold:'#b88d35',faint:'#f4f8fb',error:'#b73e42',amber:'#8b611a'};
const FONT='"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif';
const abort=(signal?:AbortSignal)=>{if(signal?.aborted)throw new DOMException('导出已取消','AbortError');};
type Asset=ImageBitmap;

function font(ctx:CanvasRenderingContext2D,size:number,bold=false){ctx.font=`${bold?'600':'400'} ${size}px ${FONT}`;ctx.textBaseline='top';}
function wrap(ctx:CanvasRenderingContext2D,text:string,width:number,size:number,bold=false):string[]{
 font(ctx,size,bold);const lines:string[]=[];
 for(const paragraph of String(text).split('\n')){
  let line='';
  // Keep Latin names together when they fit; CJK still wraps by character.
  for(const token of paragraph.match(/[A-Za-z0-9]+(?:[._'-][A-Za-z0-9]+)*|\s+|./gu)??[]){
   if(ctx.measureText(token).width<=width){if(line&&ctx.measureText(line+token).width>width){lines.push(line.trimEnd());line=token.trimStart();}else line+=token;}
   else for(const char of Array.from(token)){if(line&&ctx.measureText(line+char).width>width){lines.push(line.trimEnd());line=char;}else line+=char;}
  }
  lines.push(line);
 }
 return lines;
}
function linesHeight(ctx:CanvasRenderingContext2D,text:string,width:number,size:number,lineHeight:number,bold=false){return wrap(ctx,text,width,size,bold).length*lineHeight;}
function text(ctx:CanvasRenderingContext2D,value:string,x:number,y:number,width:number,size=18,color=COLOR.ink,lineHeight=Math.ceil(size*1.4),bold=false):number{
 const lines=wrap(ctx,value,width,size,bold);font(ctx,size,bold);ctx.fillStyle=color;
 for(const [index,line]of lines.entries())ctx.fillText(line,x,y+index*lineHeight);
 return lines.length*lineHeight;
}
function box(ctx:CanvasRenderingContext2D,x:number,y:number,w:number,h:number,fill=COLOR.paper,stroke=COLOR.line,r=10){
 ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=1.3;ctx.stroke();}
}
function image(ctx:CanvasRenderingContext2D,assets:Map<string,Asset>,src:string|null|undefined,x:number,y:number,w:number,h:number,label='?',mode:'cover'|'contain'='cover'){
 const asset=src?assets.get(src):undefined;
 ctx.save();ctx.beginPath();ctx.roundRect(x,y,w,h,5);ctx.clip();ctx.fillStyle=COLOR.faint;ctx.fillRect(x,y,w,h);
 if(asset){
  const ratio=mode==='cover'?Math.max(w/asset.width,h/asset.height):Math.min(w/asset.width,h/asset.height);
  ctx.drawImage(asset,x+(w-asset.width*ratio)/2,y+(h-asset.height*ratio)/2,asset.width*ratio,asset.height*ratio);
 }else {font(ctx,Math.min(24,w*.28),true);ctx.fillStyle=COLOR.muted;ctx.textAlign='center';ctx.fillText(label,x+w/2,y+h/2-12);}
 ctx.restore();ctx.textAlign='left';
}
function matrixSize(value:ShareImageMatrix):number {
 const rows=value?.matrix;if(!Array.isArray(rows)||rows.length<21||rows.length>220||rows.some(row=>typeof row!=='string'||row.length!==rows.length||!/^[01]+$/.test(row)))throw new Error('图片回导标记格式无效，请重新生成。');
 return rows.length*QR_PIXEL;
}
function drawMatrix(ctx:CanvasRenderingContext2D,value:ShareImageMatrix,x:number,y:number){
 const size=matrixSize(value);ctx.imageSmoothingEnabled=false;ctx.fillStyle='#ffffff';ctx.fillRect(x,y,size,size);ctx.fillStyle='#000000';
 value.matrix.forEach((row,iy)=>{for(let ix=0;ix<row.length;ix++)if(row[ix]==='1')ctx.fillRect(x+ix*QR_PIXEL,y+iy*QR_PIXEL,QR_PIXEL,QR_PIXEL);});
 ctx.imageSmoothingEnabled=true;
}

function equipImageHeight(equip:ShareEquip):number{return (equip.candidateCount??1)>1?52:72;}
function memberHeight(ctx:CanvasRenderingContext2D,member:ShareMember,w:number):number{
 let h=196+linesHeight(ctx,member.name,w-24,19,26,true)+20+24;
 if(member.skills.length)h+=62;
 if(member.append)h+=linesHeight(ctx,member.append,w-24,13,18)+6;
 if(member.equips.length)for(const equip of member.equips)h+=linesHeight(ctx,equip.label,w-24,12,18)+2+equipImageHeight(equip)+8+linesHeight(ctx,equip.name,w-24,17,23)+linesHeight(ctx,equip.details,w-24,12,17)+14;
 else h+=76;
 return h+14;
}
function subjectHeight(ctx:CanvasRenderingContext2D,person:SharePerson,width:number):number{return Math.max(58,20+linesHeight(ctx,person.name,width-65,19,25,true));}
function subject(ctx:CanvasRenderingContext2D,assets:Map<string,Asset>,person:SharePerson,x:number,y:number,width:number){
 image(ctx,assets,person.image,x,y,48,58,person.position==='御主'?'御':person.identified?'?':person.support?'助':person.slot==null?'?':'空');
 text(ctx,`${person.position}${person.support?' · 助战':''}`,x+61,y,width-61,12,COLOR.muted,17);
 text(ctx,person.name,x+61,y+20,width-61,19,COLOR.ink,25,true);
}
function skillBodyHeight(ctx:CanvasRenderingContext2D,action:ShareSkill):number{
 let h=Math.max(subjectHeight(ctx,action.actor,245),linesHeight(ctx,action.name,240,19,25,true)+22,action.target?subjectHeight(ctx,action.target,310):0);
 if(action.swap)h=Math.max(h,...action.swap.map(person=>subjectHeight(ctx,person,248)));
 return h;
}
function skillHeight(ctx:CanvasRenderingContext2D,action:ShareSkill):number{
 let h=skillBodyHeight(ctx,action);
 if(action.enemy)h+=24;if(action.choice)h+=linesHeight(ctx,`效果：${action.choice}`,CONTENT-100,16,23)+5;if(action.detail)h+=linesHeight(ctx,action.detail,CONTENT-100,15,21);
 return Math.ceil(h+28);
}
function attackHeight(ctx:CanvasRenderingContext2D,action:ShareAttack):number{
 const col=(CONTENT-48-32)/3;
 let h=50;
 for(let i=0;i<action.cards.length;i+=3){
  h+=Math.max(178,...action.cards.slice(i,i+3).map(card=>card.automatic?178:66+linesHeight(ctx,card.person?.name??'',col-152,18,24,true)+linesHeight(ctx,card.name,col-152,15,21)+24))+12;
 }
 return h+10;
}
function actionHeight(ctx:CanvasRenderingContext2D,action:ShareAction){return action.kind==='attack'?attackHeight(ctx,action):skillHeight(ctx,action);}

interface Layout {height:number;header:number;formation:number;mystic:number;turns:number[];footer:number;qrColumns:number;qrTile:number;qrSize:number}
function layout(ctx:CanvasRenderingContext2D,model:ShareImageModel,encoded:EncodedShareImage):Layout{
 if(encoded?.format!=='maafgo-share-image'||encoded.schema!==1||!Array.isArray(encoded.markers)||!encoded.markers.length)throw new Error('缺少图片回导标记，请重新生成。');
 if(encoded.markers.length>24)throw new Error('方案内容过多，一张分享图片无法容纳完整回导标记，请拆分方案。');
 const anchorSize=matrixSize(encoded.anchor);
 if(anchorSize>210)throw new Error('图片定位标记过大，请重新生成。');
 const header=Math.max(238,anchorSize+78,76+linesHeight(ctx,model.title,CONTENT-260,38,52,true)+108);
 const col=(CONTENT-5*12)/6;
 const formation=60+Math.max(...model.members.map(member=>memberHeight(ctx,member,col)));
 const mystic=Math.max(138,84+linesHeight(ctx,model.mystic.name,470,25,34,true),...model.mystic.skills.slice(0,3).map(skill=>84+linesHeight(ctx,skill.name,140,14,20)));
 const turns=model.turns.map(turn=>74+turn.actions.reduce((total,action)=>total+actionHeight(ctx,action),0)+(turn.implicitEnd?44:0)+14);
 const qrSize=Math.max(...encoded.markers.map(matrixSize)),qrColumns=qrSize+40<=(CONTENT-16)/2?2:1;
 if(qrSize+40>CONTENT)throw new Error('回导标记超出图片宽度，请拆分方案。');
 const qrTile=qrSize+70;
 const noticeHeight=model.notices.reduce((h,notice)=>h+linesHeight(ctx,notice,CONTENT-48,15,22)+6,0);
 const footer=148+Math.ceil(encoded.markers.length/qrColumns)*qrTile+noticeHeight+64;
 const height=PAD+header+20+formation+20+mystic+28+(turns.length?turns.reduce((sum,h)=>sum+h+20,0):100)+footer+BRAND_GAP+BRAND_HEIGHT+PAD;
 if(height>SHARE_IMAGE_MAX_HEIGHT||height*W>SHARE_IMAGE_MAX_PIXELS)throw new Error(`当前内容需要约 ${W}×${Math.ceil(height)} 像素，超出单张图片限制。请减少回合或拆分方案后导出，不会截掉内容。`);
 return {height:Math.ceil(height),header,formation,mystic,turns,footer,qrColumns,qrTile,qrSize};
}

function renderMember(ctx:CanvasRenderingContext2D,assets:Map<string,Asset>,member:ShareMember,x:number,y:number,w:number,h:number){
 box(ctx,x,y,w,h,member.support?'#fffcf3':COLOR.paper,member.support?COLOR.gold:COLOR.line,7);
 text(ctx,`${member.slot!+1} · ${member.slot!<3?'前排':'候补'}`,x+12,y+12,w-24,14,COLOR.blue,20,true);
 if(member.support){text(ctx,member.support,x+w-82,y+13,70,12,COLOR.amber,18,true);}
 let top=y+42;
 image(ctx,assets,member.image,x+12,top,w-24,130,member.support?'助战':member.identified?'?':'空');
 if(member.classIcon)image(ctx,assets,member.classIcon,x+15,top+96,30,30,'', 'contain');
 if(member.grand){box(ctx,x+w-76,top+108,62,18,COLOR.deep,'',2);text(ctx,'GRAND',x+w-73,top+110,57,11,'#ffffff',14,true);}
 top+=140;text(ctx,member.rarity,x+12,top,w-24,15,COLOR.gold,21,true);top+=24;
 top+=text(ctx,member.name,x+12,top,w-24,19,COLOR.ink,26,true);
 text(ctx,member.className,x+12,top+1,w-24,12,COLOR.muted,18);top+=20;
 text(ctx,member.details,x+12,top,w-24,13,COLOR.muted,20);top+=24;
 if(member.skills.length){
  const step=(w-24)/3;
  member.skills.forEach((skill,i)=>{image(ctx,assets,skill.icon,x+12+i*step,top,30,30,String(i+1),'contain');text(ctx,skill.level,x+12+i*step,top+35,step,13,COLOR.ink,18,true);});top+=62;
 }
 if(member.append){top+=text(ctx,member.append,x+12,top,w-24,13,COLOR.muted,18)+6;}
 if(!member.equips.length){box(ctx,x+12,top+4,w-24,52,COLOR.faint,COLOR.line,4);text(ctx,'不要求礼装',x+20,top+21,w-40,15,COLOR.muted,21);return;}
 for(const equip of member.equips){
  top+=text(ctx,equip.label,x+12,top,w-24,12,equip.candidateIndex?COLOR.blue:COLOR.muted,18)+2;
  const imageHeight=equipImageHeight(equip);image(ctx,assets,equip.image,x+12,top,w-24,imageHeight,'礼装','contain');top+=imageHeight+8;
  top+=text(ctx,equip.name,x+12,top,w-24,17,COLOR.ink,23,true);
  top+=text(ctx,equip.details,x+12,top,w-24,12,COLOR.muted,17)+14;
 }
}
function drawSkill(ctx:CanvasRenderingContext2D,assets:Map<string,Asset>,action:ShareSkill,x:number,y:number,w:number,height:number,ordinal:number){
 if(ordinal%2===0){ctx.fillStyle=COLOR.faint;ctx.fillRect(x+12,y,w-24,height);}
 text(ctx,String(ordinal+1).padStart(2,'0'),x+22,y+20,36,14,COLOR.muted,20);
 const sy=y+14;
 if(action.kind==='swap'){
  subject(ctx,assets,action.actor,x+64,sy,245);
  image(ctx,assets,action.icon,x+330,sy+2,42,42,action.number,'contain');
  text(ctx,'换人',x+382,sy+4,120,22,COLOR.blue,28,true);text(ctx,action.level,x+382,sy+34,120,13,COLOR.muted,18);
  if(action.swap){subject(ctx,assets,action.swap[0],x+520,sy,248);text(ctx,'⇄',x+775,sy+14,42,30,COLOR.gold,40,true);subject(ctx,assets,action.swap[1],x+830,sy,248);}
 }else if(action.kind==='retire'){
  subject(ctx,assets,action.actor,x+64,sy,245);
  text(ctx,'从者退场',x+330,sy+3,280,22,COLOR.error,29,true);
  text(ctx,'移至队伍末尾',x+330,sy+35,280,14,COLOR.muted,20);
  if(action.target){text(ctx,'→',x+702,sy+14,44,30,COLOR.blue,40,true);subject(ctx,assets,action.target,x+756,sy,310);}
 }else{
  subject(ctx,assets,action.actor,x+64,sy,245);
  image(ctx,assets,action.icon,x+330,sy+2,42,42,action.number,'contain');
  const nameH=text(ctx,action.name,x+386,sy,240,19,COLOR.ink,25,true);text(ctx,`${action.kind==='unknown'?'待检查':`技能 ${action.number}`}  ${action.level}`,x+386,sy+nameH+3,240,13,COLOR.muted,18);
  if(action.target){text(ctx,'→',x+702,sy+14,44,30,COLOR.blue,40,true);subject(ctx,assets,action.target,x+756,sy,310);}
 }
 let extra=y+14+skillBodyHeight(ctx,action)+4;
 if(action.choice)extra+=text(ctx,`效果：${action.choice}`,x+64,extra,w-100,16,COLOR.blue,23)+5;
 if(action.enemy){text(ctx,`目标：${action.enemy}`,x+64,extra,w-100,14,COLOR.error,20);extra+=24;}
 if(action.detail)text(ctx,action.detail,x+64,extra,w-100,15,COLOR.error,21);
}
function drawAttack(ctx:CanvasRenderingContext2D,assets:Map<string,Asset>,action:ShareAttack,x:number,y:number,w:number){
 text(ctx,'攻击 · 回合结束',x+24,y+10,400,20,COLOR.blue,28,true);
 if(action.enemy)text(ctx,action.enemy,x+w-300,y+13,270,15,COLOR.error,21,true);
 const col=(w-48-32)/3;let top=y+50;
 for(let start=0;start<action.cards.length;start+=3){
  const cards=action.cards.slice(start,start+3);
  const h=Math.max(178,...cards.map(card=>card.automatic?178:66+linesHeight(ctx,card.person?.name??'',col-152,18,24,true)+linesHeight(ctx,card.name,col-152,15,21)+24));
  cards.forEach((card,index)=>{
   const left=x+24+index*(col+16),tone=card.color==='buster'?'#ad484a':card.color==='arts'?'#3479b4':card.color==='quick'?'#42875b':COLOR.muted;
   box(ctx,left,top,col,h,card.automatic?COLOR.faint:COLOR.paper,card.automatic?COLOR.line:tone,6);
   text(ctx,String(start+index+1),left+10,top+9,25,13,tone,18,true);
   if(card.automatic){text(ctx,'AUTO',left+70,top+47,col-90,25,COLOR.muted,34,true);text(ctx,'默认普通卡补齐',left+54,top+100,col-70,18,COLOR.muted,26);return;}
   image(ctx,assets,card.image??card.person?.image,left+12,top+25,116,136,card.label==='宝具 NP'?'NP':'卡','contain');
   let ty=top+18;ty+=text(ctx,card.label,left+144,ty,col-155,18,tone,25,true)+6;
   if(card.person){text(ctx,card.person.position,left+144,ty,col-155,12,COLOR.muted,18);ty+=19;ty+=text(ctx,card.person.name,left+144,ty,col-155,18,COLOR.ink,24,true)+4;}
   if(card.label==='宝具 NP')ty+=text(ctx,card.name,left+144,ty,col-155,15,COLOR.muted,21);
   if(card.deckLabel)text(ctx,card.deckLabel,left+144,ty+4,col-155,12,COLOR.muted,18);
  });top+=h+12;
 }
}

async function loadAssets(urls:string[],signal?:AbortSignal):Promise<{assets:Map<string,Asset>;failures:number}>{
 const assets=new Map<string,Asset>();let pointer=0,failures=0;
 async function worker(){while(pointer<urls.length){abort(signal);const source=urls[pointer++];const controller=new AbortController(),cancel=()=>controller.abort();signal?.addEventListener('abort',cancel,{once:true});const timer=setTimeout(cancel,15000);
  try{
   const url=new URL(source,window.location.href);
   if(url.origin!==window.location.origin||url.username||url.password||(!/^\/(?:media\/|api\/(?:np-card|command-card)\?)/.test(url.pathname+url.search)&&url.href!==BRAND_ICON))throw new Error('非本地图标');
   let blob:Blob;
   if(url.pathname.startsWith('/api/'))blob=(await apiPNG(url.pathname+url.search,controller.signal)).blob;
   else{const response=await fetch(url.pathname+url.search,{credentials:'same-origin',signal:controller.signal});if(!response.ok)throw new Error('图标加载失败');blob=await response.blob();}
   const bitmap=await createImageBitmap(blob);if(signal?.aborted){bitmap.close();abort(signal);}assets.set(source,bitmap);
  }catch(error){if(signal?.aborted)throw error;failures++;}
  finally{clearTimeout(timer);signal?.removeEventListener('abort',cancel);}
 }}
 try{await Promise.all(Array.from({length:Math.min(4,urls.length)},worker));return {assets,failures};}
 catch(error){for(const asset of assets.values())asset.close();throw error;}
}
function imageSources(model:ShareImageModel):string[]{
 const urls=new Set<string>([BRAND_ICON]);const add=(url?:string|null)=>{if(url)urls.add(url);};
 model.members.forEach(member=>{add(member.image);add(member.classIcon);member.skills.forEach(skill=>add(skill.icon));member.equips.forEach(equip=>add(equip.image));});
 add(model.mystic.image);model.mystic.skills.forEach(skill=>add(skill.icon));
 const subject=(person?:SharePerson)=>add(person?.image);
 for(const turn of model.turns)for(const action of turn.actions){if(action.kind==='attack')action.cards.forEach(card=>{add(card.image);subject(card.person);});else{subject(action.actor);subject(action.target);action.swap?.forEach(subject);add(action.icon);}}
 return [...urls];
}

/** Render a standalone PNG from a frozen plan, using local assets without page capture. */
export async function renderShareImage(options:ShareImageOptions):Promise<RenderedShareImage>{
 abort(options.signal);await document.fonts?.ready;abort(options.signal);
 const model=shareImageModel(options.data,options.catalog,options);
 const canvas=document.createElement('canvas');canvas.width=W;canvas.height=1;
 const ctx=canvas.getContext('2d');if(!ctx)throw new Error('浏览器无法生成图片，请使用支持 Canvas 的桌面浏览器。');
 const geometry=layout(ctx,model,options.encoded);
 const {assets,failures}=await loadAssets(imageSources(model),options.signal);
 try{
  abort(options.signal);canvas.height=geometry.height;ctx.fillStyle=COLOR.background;ctx.fillRect(0,0,W,canvas.height);
  let top=PAD;
  box(ctx,PAD,top,CONTENT,geometry.header,COLOR.paper,COLOR.line,12);
  ctx.fillStyle=COLOR.deep;ctx.fillRect(PAD,top,6,geometry.header);
  text(ctx,'MAAFGO  ·  PARTY & BATTLE PLAN',PAD+26,top+23,CONTENT-280,15,COLOR.blue,22,true);
  const titleH=text(ctx,model.title,PAD+26,top+58,CONTENT-280,38,COLOR.ink,52,true);
  text(ctx,`${model.turns.length} 回合  ·  ${model.actions} 条动作  ·  COST ${model.cost}`,PAD+26,top+70+titleH,CONTENT-280,17,COLOR.muted,24);
  text(ctx,`${model.state}${model.warnings?` · ${model.warnings} 项提醒`:''}`,PAD+26,top+104+titleH,CONTENT-280,17,model.blocking?COLOR.error:options.validation?.valid?COLOR.blue:COLOR.amber,24,true);
  const anchorSize=matrixSize(options.encoded.anchor);drawMatrix(ctx,options.encoded.anchor,W-PAD-230+Math.floor((204-anchorSize)/2),top+16);
  text(ctx,'MaaFGO 分享图 v1',W-PAD-230,top+20+anchorSize,204,13,COLOR.muted,20,true);
  text(ctx,'保留定位标记及底部数据码',W-PAD-230,top+44+anchorSize,210,11,COLOR.muted,16);
  top+=geometry.header+20;
  text(ctx,'编队配置',PAD,top,300,26,COLOR.deep,36,true);text(ctx,'从左到右：前排 1–3 / 候补 4–6',PAD+250,top+9,CONTENT-250,15,COLOR.muted,22);top+=54;
  const col=(CONTENT-5*12)/6;
  model.members.forEach((member,index)=>renderMember(ctx,assets,member,PAD+index*(col+12),top,col,geometry.formation-60));top+=geometry.formation-54+20;
  box(ctx,PAD,top,CONTENT,geometry.mystic,COLOR.paper,COLOR.line,10);image(ctx,assets,model.mystic.image,PAD+18,top+15,72,92,'御主','contain');
  text(ctx,'御主礼装',PAD+110,top+16,470,14,COLOR.muted,20);text(ctx,model.mystic.name,PAD+110,top+44,470,25,COLOR.ink,34,true);text(ctx,model.mystic.level,PAD+110,top+geometry.mystic-28,200,14,COLOR.muted,20);
  model.mystic.skills.slice(0,3).forEach((skill,index)=>{const x=PAD+622+index*154;image(ctx,assets,skill.icon,x,top+18,40,40,String(skill.number),'contain');text(ctx,skill.name,x,top+65,140,14,COLOR.ink,20);});top+=geometry.mystic+28;
  if(!model.turns.length){box(ctx,PAD,top,CONTENT,80,COLOR.paper,COLOR.line,10);text(ctx,'未设置回合逻辑 · 全程使用通用自动战斗',PAD+24,top+25,CONTENT-48,21,COLOR.muted,30);top+=100;}
  model.turns.forEach((turn,index)=>{
   const h=geometry.turns[index];box(ctx,PAD,top,CONTENT,h,COLOR.paper,COLOR.line,10);box(ctx,PAD+20,top+17,46,40,COLOR.deep,'',6);text(ctx,String(turn.number).padStart(2,'0'),PAD+28,top+24,34,20,'#ffffff',28,true);
   text(ctx,`第 ${turn.number} 回合`,PAD+82,top+22,500,25,COLOR.deep,34,true);text(ctx,'固定回合计划',W-PAD-170,top+28,145,14,COLOR.muted,20);
   let actionY=top+74;
   turn.actions.forEach((action,ordinal)=>{const height=actionHeight(ctx,action);if(action.kind==='attack')drawAttack(ctx,assets,action,PAD,actionY,CONTENT);else drawSkill(ctx,assets,action,PAD,actionY,CONTENT,height,ordinal);actionY+=height;});
   if(turn.implicitEnd)text(ctx,'本回合未指定攻击组，结束时由默认策略补卡。',PAD+26,actionY+8,CONTENT-52,15,COLOR.amber,22);
   top+=h+20;
  });
  box(ctx,PAD,top,CONTENT,geometry.footer,COLOR.paper,COLOR.line,10);
  text(ctx,'MaaFGO 原图回导标记 · v1',PAD+24,top+20,CONTENT-48,24,COLOR.deep,34,true);
  text(ctx,'编辑器“导入”中上传本图或 Ctrl+V，可还原编队与战斗内容。请保留整张原图，尤其是定位标记和全部数据码。',PAD+24,top+64,CONTENT-48,16,COLOR.muted,24);
  let qrY=top+124;const cell=(CONTENT-48-(geometry.qrColumns-1)*16)/geometry.qrColumns;
  options.encoded.markers.forEach((marker,index)=>{
   const row=Math.floor(index/geometry.qrColumns),column=index%geometry.qrColumns,x=PAD+24+column*(cell+16),y=qrY+row*geometry.qrTile;
   box(ctx,x,y,cell,geometry.qrTile-12,'#ffffff',COLOR.line,6);const size=matrixSize(marker);drawMatrix(ctx,marker,Math.round(x+(cell-size)/2),Math.round(y+10));
   text(ctx,`回导标记 ${marker.index+1} / ${marker.total}`,x+20,y+geometry.qrSize+23,cell-40,15,COLOR.muted,22,true);
  });
  qrY+=Math.ceil(options.encoded.markers.length/geometry.qrColumns)*geometry.qrTile;
  for(const notice of model.notices)qrY+=text(ctx,notice,PAD+24,qrY+4,CONTENT-48,15,COLOR.amber,22)+6;
  text(ctx,'本图仅记录固定回合计划，实际技能、NP及选卡以游戏为准。未指定面卡和不可用宝具由当前策略补齐。',PAD+24,qrY+10,CONTENT-48,14,COLOR.muted,21);
  top+=geometry.footer+BRAND_GAP;
  box(ctx,PAD,top,CONTENT,BRAND_HEIGHT,COLOR.paper,COLOR.line,10);
  image(ctx,assets,BRAND_ICON,PAD+24,top+24,120,120,'MaaFGO','contain');
  text(ctx,'MaaFGO',PAD+172,top+24,CONTENT-196,29,COLOR.deep,40,true);
  text(ctx,`GitHub：${PROJECT_URL}`,PAD+172,top+72,CONTENT-196,21,COLOR.muted,30);
  text(ctx,'B站搜索：是kumi啦',PAD+172,top+111,CONTENT-196,23,COLOR.blue,32,true);
  abort(options.signal);
  const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('图片编码失败，请重试。')),'image/png'));
  abort(options.signal);
  if(blob.size>16*1024*1024)throw new Error('生成的 PNG 超过16 MiB导入限制，请拆分方案后导出。');
  return {blob,width:W,height:geometry.height,warnings:[...model.notices,...(failures?[`有 ${failures} 项图标未能加载，图片已保留对应的文字说明；回导数据不受影响。`]:[])]};
 }finally{for(const asset of assets.values())asset.close();canvas.width=canvas.height=1;}
}
