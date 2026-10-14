"use client";
import { useId, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { MathText } from "@/components/math-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { BlockState, StepBlock } from "@/lib/ui-blocks";
import type { EventIntent } from "@/lib/ui-events";
const faNumber=(value:number)=>new Intl.NumberFormat("fa-IR").format(value);

export function StepReveal({block,state,onChange,onAsk,onEvent,disabled=false}:{block:StepBlock;state?:BlockState;onChange:(state:BlockState)=>void;onAsk:(text:string)=>void;onEvent?:(event:EventIntent)=>void;disabled?:boolean}) {
  const id=useId(), [question,setQuestion]=useState(false);
  const index=state?.kind==="step_reveal" && Number.isInteger(state.index) ? Math.max(0,Math.min(block.params.steps.length-1,state.index)) : 0;
  const current=block.params.steps[index], previous=block.params.steps[index-1];
  const go=(next:number)=>{onChange({kind:"step_reveal",index:next});setQuestion(false);};
  return <Card className="ui-block step-reveal" data-block-id={block.id} role="region" aria-labelledby={`${id}-title`} dir="rtl">
    <CardHeader><CardTitle><h2 id={`${id}-title`} dir="auto">{block.title}</h2></CardTitle><CardDescription>تغییر هر مرحله را ببینید و با سرعت خودتان پیش بروید.</CardDescription></CardHeader>
    <CardContent><div className="reveal-position"><span role="status" aria-live="polite">مرحلهٔ {faNumber(index+1)} از {faNumber(block.params.steps.length)}</span><Badge variant={current.verification==="verified" ? "secondary":"outline"}>{current.verification==="verified" ? "بررسی‌شده" : "بررسی ماشینی نشده"}</Badge></div>
      <div className="reveal-equations" key={current.step_id}>
        {previous && <div className="previous-equation" role="group" aria-label="مرحلهٔ قبل"><MathText text={`$$${previous.state}$$`}/></div>}
        <div className="current-equation" data-testid="current-step" role="group" aria-label="مرحلهٔ فعلی"><ChangedEquation current={current.state} previous={previous?.state}/></div>
        <p className="step-justification" dir="auto">{current.justification}</p>
        {current.verification!=="verified" && <p className="block-note">{current.verification==="unknown" ? "درستی این تغییر هنوز قطعی نشده است؛ آن را جداگانه بررسی کنید." : "این تغییر با روش موجود بررسی نشده است؛ آن را جداگانه بررسی کنید."}</p>}
      </div>
      {question && !onEvent && <p className="block-note" role="status">پرسش این مرحله در کادر پیام آماده شد. برای دریافت توضیح، آن را ارسال کنید.</p>}
    </CardContent><CardFooter className="reveal-controls"><Button variant="outline" size="sm" disabled={disabled || index===0} onClick={()=>go(index-1)}><ChevronRight data-icon="inline-start"/>مرحلهٔ قبل</Button><Button size="sm" disabled={disabled || index===block.params.steps.length-1} onClick={()=>go(index+1)}>مرحلهٔ بعد<ChevronLeft data-icon="inline-end"/></Button><Button variant="ghost" size="sm" disabled={disabled} onClick={()=>{if(onEvent)onEvent({type:"step_confused",block_id:block.id,payload:{step_id:current.step_id}});else onAsk(`این مرحله را ساده‌تر توضیح بده: $${current.state}$. ${current.justification}`);setQuestion(true);}}>این مرحله را نفهمیدم</Button></CardFooter>
  </Card>;
}

function ChangedEquation({current,previous}:{current:string;previous?:string}) {
  const sides=current.split(" = "), before=previous?.split(" = ");
  if(sides.length!==2 || before?.length!==2) return <div className={previous && current!==previous ? "changed-math":""}><MathText text={`$$${current}$$`}/></div>;
  return <div className="equation-sides" dir="ltr"><span className={sides[0]!==before[0] ? "changed-math":""}><MathText text={`$${sides[0]}$`}/></span><MathText text="$=$"/><span className={sides[1]!==before[1] ? "changed-math":""}><MathText text={`$${sides[1]}$`}/></span></div>;
}
