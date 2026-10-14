"use client";
import {useState} from "react";
import {Brain} from "lucide-react";
import {Button} from "@/components/ui/button";
import {Badge} from "@/components/ui/badge";
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription,DialogFooter} from "@/components/ui/dialog";
import {Field,FieldGroup,FieldLabel} from "@/components/ui/field";
import {Select,SelectTrigger,SelectValue,SelectContent,SelectGroup,SelectItem} from "@/components/ui/select";
import {Separator} from "@/components/ui/separator";
import type {LearnerProfile} from "@/lib/learner-profile";
import type {Level} from "@/lib/contracts";
export const topicLabels:Record<string,string>={derivative:"مشتق",integral:"انتگرال",limits:"حد",algebra:"جبر",matrix:"ماتریس",probability:"احتمال",optimization:"بهینه‌سازی",logarithms:"لگاریتم",exponentials:"توان و تابع نمایی",trigonometry:"مثلثات",geometry:"هندسه",mathematics:"ریاضی"};
const labels:Record<Level,string>={beginner:"مبتدی",intermediate:"متوسط",advanced:"پیشرفته"};
const faNumber=(n:number)=>new Intl.NumberFormat("fa-IR").format(n);

export function LearnerMemory({profile,disabled,onCorrect,onReset}:{profile:LearnerProfile;disabled:boolean;onCorrect:(topic:string,level:Level)=>void|Promise<void>;onReset:()=>Promise<void>}){
  const [open,setOpen]=useState(false),[resetting,setResetting]=useState(false),[notice,setNotice]=useState("");
  const [draft,setDraft]=useState<Record<string,Level>>({}),[saving,setSaving]=useState(false);
  const entries=Object.entries(profile.topics).sort(([,a],[,b])=>Date.parse(b.last_seen||"")-Date.parse(a.last_seen||""));
  return <><Button variant="ghost" size="icon" className="memory-trigger" aria-label="حافظه یادگیری" title="حافظه یادگیری" aria-haspopup="dialog" aria-expanded={open} onClick={()=>{setNotice("");setDraft({});setOpen(true);}}><Brain strokeWidth={1.7}/></Button>
    <Dialog open={open} onOpenChange={value=>{if(!saving&&!resetting)setOpen(value);}}><DialogContent dir="rtl" className="learner-memory-dialog"><DialogHeader><DialogTitle>حافظه یادگیری</DialogTitle><DialogDescription>این حافظه در همین مرورگر ذخیره می‌شود. برآورد سطح تقریبی است و آزمون مهارت نیست؛ هر زمان می‌توانید آن را اصلاح کنید.</DialogDescription></DialogHeader>
      <p className="block-note">{faNumber(entries.length)} موضوع ذخیره‌شده</p>
      <div className="learner-topic-list"><FieldGroup>{entries.map(([key,entry])=><Field key={key} className="learner-topic"><div className="learner-topic-heading"><FieldLabel htmlFor={`memory-${key}`} dir="auto">{topicLabels[key]||key}</FieldLabel><Badge variant="outline">{entry.level_source==="manual"?"انتخاب شما":"برآوردی"}</Badge></div>
        <Select dir="rtl" value={draft[key]||entry.level} onValueChange={value=>setDraft(previous=>({...previous,[key]:value as Level}))} disabled={disabled||resetting||saving}><SelectTrigger id={`memory-${key}`} aria-label={`سطح ${topicLabels[key]||key}`}><SelectValue/></SelectTrigger><SelectContent><SelectGroup>{Object.entries(labels).map(([value,label])=><SelectItem value={value} key={value}>{label}</SelectItem>)}</SelectGroup></SelectContent></Select>
        {!!entry.confusion_spots.length&&<details><summary>{faNumber(entry.confusion_spots.length)} نکته برای مرور</summary><ul>{entry.confusion_spots.map((spot,index)=><li key={index} dir="auto">{spot.concept} · {faNumber(spot.count)} بار</li>)}</ul></details>}
        {entry.last_seen&&<p className="block-note">آخرین مرور: {new Intl.DateTimeFormat("fa-IR",{dateStyle:"medium"}).format(new Date(entry.last_seen))}</p>}
      </Field>)}</FieldGroup>{!entries.length&&<p>با شروع یک درس، سطح و نکته‌های نیازمند مرور در اینجا ثبت می‌شوند.</p>}</div>
      <Separator/>{notice&&<p role="status">{notice}</p>}<DialogFooter><Button disabled={disabled||resetting||saving} onClick={async()=>{setSaving(true);setNotice("");try{for(const [topic,level] of Object.entries(draft)){if(profile.topics[topic])await onCorrect(topic,level);}setDraft({});setOpen(false);}catch{setNotice("ذخیرهٔ حافظه انجام نشد؛ دوباره تلاش کنید.");}finally{setSaving(false);}}}>{saving?"در حال ذخیره…":"ذخیره"}</Button><Button variant="outline" disabled={resetting||saving} onClick={()=>setOpen(false)}>بستن</Button><Button variant="destructive" disabled={disabled||resetting||saving||!entries.length} onClick={async()=>{setResetting(true);try{await onReset();setDraft({});setNotice("حافظه پاک شد. گفت‌وگوها و تنظیمات درس محفوظ هستند.");}catch{setNotice("پاک کردن حافظه انجام نشد؛ دوباره تلاش کنید.");}finally{setResetting(false);}}}>پاک کردن حافظه</Button></DialogFooter>
    </DialogContent></Dialog></>;
}
