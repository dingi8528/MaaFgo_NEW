import type {Json} from './model';

const positiveId=(id:unknown):id is number=>typeof id==='number'&&Number.isSafeInteger(id)&&id>0;
const supportRole=(member:Json|null|undefined)=>String(member?.supportType??'').toLowerCase();
const isSupportRole=(role:string)=>['friend','npc','fixed'].includes(role);

export function hasServantIdentity(member:Json|null|undefined):member is Json&{svtId:number} {
 return positiveId(member?.svtId);
}

export function isUnspecifiedSupport(member:Json|null|undefined):boolean {
 if(!member||supportRole(member)!=='friend'||(member.svtId!=null&&member.svtId!==0))return false;
 // Keep explicit candidate requests visible so the editor can report invalid ones.
 const hasCandidates=['equip1','equip2','equip3'].some(key=>{
  const candidates=member[key]?.candidates;
  return Array.isArray(candidates)?candidates.length>0:!!candidates;
 });
 return hasCandidates||positiveId(member.equip1?.id)||positiveId(member.ceId)||
  (member.grandSvt===true&&(positiveId(member.equip3?.id)||typeof member.classBoardData?.grandBondEquipSkillChange==='boolean'));
}

export function isSupportMember(member:Json|null|undefined):boolean {
 return isSupportRole(supportRole(member))&&(hasServantIdentity(member)||isUnspecifiedSupport(member));
}

function visibleMember(member:Json|null|undefined):Json|null {
 if(member==null)return null;
 // Keep malformed records visible to validation and COST inspection.
 if(typeof member!=='object'||Array.isArray(member))return member;
 if(!Object.keys(member).length)return null;
 if((member.svtId==null||member.svtId===0)&&isSupportRole(supportRole(member))&&!isUnspecifiedSupport(member))return null;
 return member;
}

/** Keep the six positions and original JSON, but drop empty role flags from editor views. */
export function partyMembers(data:Json):(Json|null)[] {
 return ['onFieldSvts','backupSvts'].flatMap(key=>{
  const group=data.team?.[key];
  return Array.from({length:3},(_,index)=>visibleMember(Array.isArray(group)?group[index]:null));
 });
}
