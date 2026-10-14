"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUp, Check, ChevronLeft, Download, Ellipsis, Menu, Moon, Plus, Search, Sigma, Square, Sun, Trash2, Pencil, RotateCcw, X, BookOpenText, Sparkles, PanelRightClose, PanelRightOpen } from "lucide-react";
import { cn } from "cn";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Field, FieldLabel } from "@/components/ui/field";
import { Conversation, ConversationContent, ConversationScrollButton } from "@/components/ai-elements/conversation";
import { Message as MessageRow, MessageContent } from "@/components/ai-elements/message";
import { MathText } from "./math-text";
import { BlockRenderer } from "./blocks/block-renderer";
import { newChat, threadId, type Chat, type Action, type EndEvent, type Level, type PendingTurn, type StreamEvent } from "@/lib/contracts";
import { loadChats, saveChat, deleteChat, exportChats, getSetting, setSetting } from "@/lib/storage";
import { streamTurn, StreamError } from "@/lib/stream";
import { createUIEvent, describeEvent, EventRateLimit, type EventIntent, type UIEvent, type LocalEventIntent } from "@/lib/ui-events";
import {LearnerMemory} from "./learner-memory";
import {emptyProfile,trimProfile,correctLevel,automaticLevel,levelSchema,topicEntry,type LearnerProfile} from "@/lib/learner-profile";
import {loadLearnerProfile,saveLearnerProfile,rememberLearnerTurn,resetLearnerProfile} from "@/lib/storage";
import {blockSchema} from "@/lib/ui-blocks";

const levels: Record<Level,string> = {beginner: "مبتدی", intermediate: "متوسط", advanced: "پیشرفته"};
const phases: Record<string,string> = {queued: "در صف پاسخ…", classifying: "در حال فهم پرسش…", retrieving: "در حال آماده‌سازی درس…", computing: "در حال محاسبه…", writing: "در حال نوشتن…", validating_block: "در حال آماده‌سازی نمودار و مراحل…", waiting_for_user: "نوبت شماست", done: "پاسخ آماده است"};
const errors: Record<string,string> = {network_error: "ارتباط با معلم برقرار نشد. اتصال و سرویس را بررسی کنید.", stream_interrupted: "دریافت پاسخ متوقف شد. می‌توانید همین پاسخ را دوباره دریافت کنید.", bad_request: "درخواست پذیرفته نشد. متن یا تنظیمات را بررسی کنید.", turn_timeout: "آماده‌سازی پاسخ بیش از حد طول کشید.", turn_in_progress: "پاسخ قبلی هنوز در حال آماده‌سازی است. کمی بعد دوباره تلاش کنید.", internal_error: "پاسخ در دسترس نیست. متن گفت‌وگو محفوظ است."};
const faNumber = (n: number) => new Intl.NumberFormat("fa-IR").format(n);
errors.session_limit = "سقف استفاده از این جلسه رسیده است. می‌توانید گفت‌وگوی تازه‌ای شروع کنید.";
const suggestions = [{title: "لگاریتم را بفهمم", detail: "از معنی توان تا قواعد لگاریتم", query: "لگاریتم را از ابتدا به من توضیح بده"}, {title: "با مشتق آشنا شوم", detail: "تغییر، شیب و ایدهٔ مشتق", query: "مفهوم مشتق را از ابتدا توضیح بده"}, {title: "یک معادله حل کنم", detail: "راه‌حل را قدم‌به‌قدم ببینم", query: "معادله 2x+5=17 را مرحله به مرحله توضیح بده"}];

function ThreadViewport({empty,children}: {empty:boolean;children:ReactNode}) {
  if(empty) return <div className="welcome-scroll"><div className="conversation-content">{children}</div></div>;
  return <Conversation className="conversation"><ConversationContent className="conversation-content">{children}</ConversationContent><ConversationScrollButton aria-label="رفتن به آخرین پیام"/></Conversation>;
}

export function TutorShell() {
  const [chats,setChats] = useState<Chat[]>([]), [active,setActive] = useState(""), [loaded,setLoaded] = useState(false);
  const [input,setInput] = useState(""), [search,setSearch] = useState(""), [busy,setBusy] = useState(false), [phase,setPhase] = useState("");
  const [error,setError] = useState(""), [storageError,setStorageError] = useState(false), [dark,setDark] = useState(false), [sidebar,setSidebar] = useState(false);
  const [libraryCollapsed,setLibraryCollapsed] = useState(false);
  const [desktopLayout,setDesktopLayout] = useState(true);
  useEffect(() => {
    const query = matchMedia("(min-width:761px)");
    const updateLayout = () => setDesktopLayout(query.matches);
    updateLayout(); query.addEventListener("change", updateLayout);
    return () => query.removeEventListener("change", updateLayout);
  }, []);
  useEffect(() => {
    if (!sidebar || desktopLayout) return;
    document.querySelector<HTMLButtonElement>('.brand .mobile-only')?.focus();
    const closeWithEscape = (event: KeyboardEvent) => {
      if(event.key === "Escape") {
        setSidebar(false);
        document.querySelector<HTMLButtonElement>('.header-title .mobile-only')?.focus();
      }
    };
    document.addEventListener("keydown", closeWithEscape);
    return () => document.removeEventListener("keydown", closeWithEscape);
  }, [sidebar,desktopLayout]);
  const [editing,setEditing] = useState<Chat|null>(null), [rename,setRename] = useState(""), [deleting,setDeleting] = useState<Chat|null>(null);
  const [saving,setSaving]=useState(false), saveRevision=useRef(0);
  const [degraded,setDegraded]=useState(false);
  useEffect(()=>setDegraded(false),[active]);
  const controller = useRef<AbortController|null>(null), busyRef = useRef(false), inputRef = useRef<HTMLTextAreaElement>(null);
  const chat = chats.find(item => item.id === active);
  const selectedRef = useRef(chat); selectedRef.current = chat;
  const eventLimit=useRef(new EventRateLimit());
  const [profile,setProfile]=useState<LearnerProfile>(emptyProfile),profileRef=useRef(profile),profileWrites=useRef<Promise<unknown>>(Promise.resolve());
  profileRef.current=profile;
  const writeProfile=(next:LearnerProfile)=>{profileRef.current=next;setProfile(next);const persist=profileWrites.current.catch(()=>{}).then(()=>saveLearnerProfile(next));profileWrites.current=persist.catch(()=>setStorageError(true));return persist;};

  useEffect(() => {
    let alive = true;
    Promise.all([loadChats(), getSetting("active"), getSetting("theme"),loadLearnerProfile()]).then(([saved,id,theme,memory]) => {
      if (!alive) return;
      const list = saved.length ? saved.map(row=>({...row,manualLevel:row.manualLevel??(!row.levelSource&&row.level!=="beginner"?row.level:undefined)})) : [newChat()];
      setProfile(memory);profileRef.current=memory;
      setChats(list); setActive(list.some(item => item.id === id) ? id! : list[0].id);
      setDark(theme === "dark" || (!theme && matchMedia("(prefers-color-scheme: dark)").matches)); setLoaded(true);
    }).catch(() => { if (alive) {const fresh = newChat(); setChats([fresh]); setActive(fresh.id); setStorageError(true); setLoaded(true);} });
    return () => { alive = false; controller.current?.abort(); };
  }, []);
  useEffect(() => { document.documentElement.dataset.theme = dark ? "dark" : "light"; document.documentElement.classList.toggle("dark",dark); if (loaded) void setSetting("theme",dark ? "dark" : "light").catch(() => setStorageError(true)); }, [dark,loaded]);
  useEffect(() => {
    if (!loaded || !chat) return;
    const revision=++saveRevision.current;setSaving(true);
    const timer = setTimeout(() => {
      void Promise.all([saveChat(chat),setSetting("active",active)]).catch(()=>setStorageError(true))
        .finally(()=>{if(saveRevision.current===revision)setSaving(false);});
    }, 200);
    return () => clearTimeout(timer);
  }, [chat,active,loaded]);
  const update = (id: string, change: (previous: Chat) => Chat) => setChats(list => list.map(item => item.id === id ? change(item) : item));
  const freshChat = () => { const fresh = newChat(); setChats(list => [fresh,...list]); setActive(fresh.id); setInput(""); setError(""); setSidebar(false); inputRef.current?.focus(); };
  const changeSetting = (key: "level" | "delivery" | "mode", value: string) => {
    if(!chat||!value)return;
    if(key==="level"){
      const manual=value==="auto"?undefined:value as Level;
      update(chat.id,old=>({...old,manualLevel:manual,...(manual?{level:manual,levelSource:"manual" as const}:{level:"beginner" as const,levelSource:"default" as const,levelSuggestion:null})}));
      if(chat.topic)writeProfile(manual?correctLevel(profileRef.current,chat.topic,manual):automaticLevel(profileRef.current,chat.topic));
    }else update(chat.id,old=>({...old,[key]:value}));
  };
  const correctTopic=(topic:string,level:Level)=>{
    const persist=writeProfile(correctLevel(profileRef.current,topic,level));
    if(chat?.topic===topic)update(chat.id,old=>({...old,manualLevel:level,level,levelSource:"manual"}));
    return persist;
  };
  const resetProfile=async()=>{
    await profileWrites.current;const cleared=await resetLearnerProfile();profileRef.current=cleared;setProfile(cleared);
    setChats(rows=>rows.map(row=>{if(!row.pending?.request.learner_profile)return row;const {learner_profile,...request}=row.pending.request;return {...row,pending:{...row.pending,request}};}));
  };
  const changeBlock = (messageId: string, blockId: string, state: import("@/lib/ui-blocks").BlockState) => {
    if(chat) update(chat.id,old=>({...old,messages:old.messages.map(message=>message.id===messageId ? {...message,blocks:message.blocks?.map(block=>block.id===blockId ? {...block,state}:block)} : message)}));
  };
  const askFromBlock = (question: string) => {setInput(question.slice(0,8000));inputRef.current?.focus();};
  const localFromBlock=(intent:LocalEventIntent)=>{
    const current=selectedRef.current;
    if(current)update(current.id,old=>{
      const seq=(old.eventSeq || 0)+1;
      return {...old,eventSeq:seq,uiHistory:[...(old.uiHistory || []),{...intent,seq,sent_at:new Date().toISOString()}].slice(-128)};
    });
  };
  const eventFromBlock = (intent:EventIntent) => {
    const current=selectedRef.current;
    if(!current || busyRef.current || current.expired || !current.lesson?.awaiting_user || current.pending)return;
    if(!eventLimit.current.allow(current.threadId)){setError("کمی صبر کنید و دوباره دربارهٔ این بخش بپرسید.");return;}
    const seq=(current.eventSeq || 0)+1;
    const event=createUIEvent(intent,current.threadId,seq);
    void send("ui_event",describeEvent(intent,current.language!=="en"),undefined,false,event);
  };

  async function send(action: Action, text = "", retry?: PendingTurn, recovery = false,uiEvent?:UIEvent) {
    const current = selectedRef.current;
    if (!current || busyRef.current || (!text.trim() && ["new_lesson","followup"].includes(action))) return;
    busyRef.current = true; setBusy(true); setError(""); setPhase("queued");
    const nextThread = recovery ? threadId() : current.threadId;
    await profileWrites.current;
    const job: PendingTurn = retry || {requestId: crypto.randomUUID(), messageId: crypto.randomUUID(),startedAt:Date.now(), request: {thread_id: nextThread, message: action==="ui_event" ? "" : text.trim(), action, mode: current.mode, delivery: current.delivery,...(current.manualLevel?{level:current.manualLevel,level_source:"manual" as const}:{level_source:"inferred" as const}),learner_profile:trimProfile(profileRef.current,current.topic),...(uiEvent ? {ui_event:uiEvent}:{})}};
    const original = current.messages;
    let runningChat: Chat = {...current, threadId: nextThread, eventSeq:recovery ? 0 : Math.max(current.eventSeq || 0,job.request.ui_event?.seq || 0), expired: false, pending: job, updatedAt: Date.now(), title: current.messages.length ? current.title : text.slice(0,42),
      messages: retry ? current.messages.map(m => m.id === job.messageId ? {...m, segments: [], partial: true} : m) : [...current.messages,
        ...(recovery ? [{id: crypto.randomUUID(), role: "system" as const, segments: [{kind: "text" as const, text: "ادامهٔ گفت‌وگو در یک جلسهٔ تازه"}]}] : []),
        ...(text && !recovery ? [{id: crypto.randomUUID(),role: "user" as const,segments: [{kind: "text" as const,text}]}] : []),
        {id: job.messageId,role: "assistant",segments: [],partial: true}]};
    const publish = (change: (old: Chat) => Chat) => { runningChat = change(runningChat); const snapshot = runningChat; update(current.id, () => snapshot); };
    update(current.id, () => runningChat);
    // Save the replay identity before sending, so a reload cannot lose it.
    await saveChat(runningChat).catch(() => setStorageError(true));
    setInput(""); const abort = new AbortController(); controller.current = abort;
    let ended = false, serverError = false;
    let memorySave:Promise<unknown>=Promise.resolve();
    try {
      await streamTurn(job,abort.signal, ({event,data}: StreamEvent) => {
        if (event === "status") setPhase(String(data.state));
        if (event === "text") {
          const index = data.segment_index, kind = data.kind, delta = data.delta;
          if (typeof index !== "number" || !Number.isInteger(index) || index < 0 || index > 100 || typeof delta !== "string" || !["text","answer"].includes(String(kind))) return;
          publish(old => ({...old,messages: old.messages.map(m => {
            if(m.id !== job.messageId) return m;
            const segments = [...m.segments]; segments[index] = {kind: kind as "text"|"answer",text: (segments[index]?.text || "") + delta};
            return {...m,segments};
          })}));
        }
        if(event === "error") {serverError = true; setError(errors[String(data.code)] || errors.internal_error);}
        if(event === "block" && data.block && typeof data.block === "object") {
          const raw=data.block as Record<string,unknown>;
          publish(old=>({...old,messages:old.messages.map(message=>{
            if(message.id!==job.messageId) return message;
            const blocks=[...(message.blocks || [])];
            const id=typeof raw.id==="string" && raw.id.length<=64 ? raw.id : `visual-${blocks.length}`;
            const index=blocks.findIndex(block=>block.id===id);
            if(index>=0) blocks[index]={...blocks[index],payload:raw};
            else if(blocks.length<2) blocks.push({id,payload:raw});
            return {...message,blocks};
          })}));
        }
        if(event === "turn_end") {
          ended = true; const end = data as unknown as EndEvent;
          setDegraded(data.degraded===true);
          if((data.usage as {limit_reached?:boolean}|undefined)?.limit_reached)setError(errors.session_limit);
          if(!serverError&&end.status==="ok"&&end.mode==="learn"&&end.topic&&end.turn_id&&levelSchema.safeParse(end.learner_level).success&&!['duplicate','stale'].includes(end.event_status||"")){
            const confused=job.request.action==="simplify"||job.request.ui_event?.type==="step_confused"||/did(?:n't| not) understand|confused|don't understand|نفهم|نمی[‌ ]?فهم|متوجه نشد/i.test(job.request.message);
            let concept=end.lesson?.concept||end.topic,stepId:string|undefined;
            if(job.request.ui_event?.type==="step_confused"){
              stepId=job.request.ui_event.payload.step_id;
              for(const message of runningChat.messages)for(const entry of message.blocks||[])if(entry.id===job.request.ui_event.block_id){
                const parsed=blockSchema.safeParse(entry.payload);
                if(parsed.success&&parsed.data.type==="step_reveal")concept=parsed.data.params.steps.find(step=>step.step_id===stepId)?.justification||concept;
              }
            }
            memorySave=rememberLearnerTurn({id:end.turn_id,startedAt:job.startedAt||0,topic:end.topic,level:end.learner_level!,source:end.level_source==="manual"?"manual":"inferred",spot:confused?{concept,step_id:stepId}:undefined})
              .then(next=>{profileRef.current=next;setProfile(next);}).catch(()=>setStorageError(true));
          }
          publish(old => ({...old, expired: end.status === "thread_not_found", pending: serverError ? old.pending : undefined,
            lesson: end.lesson || old.lesson, topic: end.topic || old.topic, language:end.language || old.language,level:end.learner_level||old.level,levelSource:end.level_source||old.levelSource,levelSuggestion:end.level_suggestion, updatedAt: Date.now(),
            messages: old.messages.map(m => m.id === job.messageId ? {...m,partial: serverError,
              segments: !m.segments.length && action === "done" ? [{kind: "text",text: "این درس به پایان رسید. برای یادگیری موضوع دیگری، گفت‌وگوی تازه بسازید."}] : m.segments} : m)}));
        }
      });
    } catch (failure) {
      setError(abort.signal.aborted ? "دریافت پاسخ متوقف شد. برای دریافت ادامه، دوباره تلاش کنید." : errors[failure instanceof StreamError ? failure.code : "network_error"] || errors.stream_interrupted);
    } finally {
      await memorySave;
      await saveChat(runningChat).catch(() => setStorageError(true));
      setBusy(false); busyRef.current = false; controller.current = null; if(!ended) setPhase("");
      // Preserve the request ID for exact replay after a disconnect or reload.
      if (!ended && !retry && original.length === 0) inputRef.current?.focus();
    }
  }
  const recover = () => {
    if(!chat) return;
    const summary = chat.messages.filter(m => m.role !== "system").slice(-8).map(m => `${m.role === "user" ? "پرسش" : "توضیح"}: ${m.segments.map(s => s.text).join("\n")}`).join("\n").slice(-5800);
    void send("new_lesson", `این گفت‌وگوی ذخیره‌شده را به‌عنوان زمینه در نظر بگیر و درس ${chat.topic || "ریاضی"} را ادامه بده:\n${summary}`, undefined, true);
  };
  const visible = chats.filter(item => `${item.title} ${item.messages.flatMap(m => m.segments.map(s => s.text)).join(" ")}`.toLowerCase().includes(search.toLowerCase()));
  const paused = !!chat?.lesson?.awaiting_user;
  return <div className={cn("study-app", libraryCollapsed && "library-collapsed")}>
    <a href="#prompt" className="skip-link">رفتن به کادر پرسش</a>
    <aside id="chat-library" className={cn("library", sidebar && "library-open")} inert={desktopLayout ? libraryCollapsed : !sidebar} aria-hidden={desktopLayout ? libraryCollapsed : !sidebar} aria-label="کتابخانه گفت‌وگوها">
      <div className="brand"><span className="brand-mark"><Sigma aria-hidden="true" /></span><div><strong>هم‌درس</strong><span>همراه یادگیری ریاضی</span></div><Button variant="ghost" size="icon" className="mobile-only" aria-label="بستن فهرست" onClick={() => setSidebar(false)}><X /></Button></div>
      <Button variant="newChat" className="new-chat" disabled={busy || !loaded} onClick={freshChat}><Plus data-icon="inline-start"/>گفت‌وگوی تازه</Button>
      <div className="search"><Search aria-hidden="true"/><Input aria-label="جست‌وجوی گفت‌وگوها" placeholder="جست‌وجو در گفت‌وگوها" value={search} onChange={e => setSearch(e.target.value)}/></div>
      <div className="library-heading"><span>گفت‌وگوهای شما</span></div>
      <nav className="chat-list">{visible.map(item => <div className={`chat-item ${item.id === active ? "selected" : ""}`} key={item.id}>
        <button disabled={busy} className="chat-select" aria-label={`باز کردن ${item.title}`} aria-current={item.id === active ? "page" : undefined} onClick={() => {setActive(item.id);setInput("");setError("");setSidebar(false);}}><span className="chat-book" aria-hidden="true"><BookOpenText strokeWidth={1.6}/></span><span>{item.title}</span></button>
        <Button variant="ghost" size="icon" aria-label={`تغییر نام ${item.title}`} disabled={busy} onClick={() => {setEditing(item);setRename(item.title);}}><Pencil/></Button>
        <Button variant="ghost" size="icon" aria-label={`حذف ${item.title}`} disabled={busy} onClick={() => setDeleting(item)}><Trash2/></Button>
      </div>)}</nav>
      <div className="library-footer"><span className="local-dot"/><span role="status">{saving ? "در حال ذخیرهٔ گفت‌وگو…" : "گفت‌وگوها روی این دستگاه ذخیره می‌شوند"}</span><Button variant="ghost" size="icon" aria-label="خروجی گفت‌وگوها" disabled={!loaded} onClick={() => exportChats(chats)}><Download/></Button></div>
    </aside>
    <button className={cn("sidebar-backdrop", sidebar && "is-open")} inert={!sidebar || desktopLayout} aria-hidden={!sidebar || desktopLayout} tabIndex={-1} aria-label="بستن فهرست" onClick={() => setSidebar(false)}/>
    <main className={cn("workspace", !chat?.messages.length && "workspace-empty")}>
      <header className="workspace-header"><div className="header-title"><Button variant="ghost" size="icon" className="mobile-only" aria-label="نمایش فهرست" aria-controls="chat-library" aria-expanded={sidebar} onClick={() => setSidebar(true)}><Menu/></Button><Button variant="ghost" size="icon" className="desktop-only library-toggle" aria-label={libraryCollapsed ? "نمایش کتابخانه" : "جمع کردن کتابخانه"} aria-controls="chat-library" aria-expanded={!libraryCollapsed} onClick={() => setLibraryCollapsed(value => !value)}>{libraryCollapsed ? <PanelRightOpen/> : <PanelRightClose/>}</Button>{chat?.messages.length ? <h1>{chat.title}</h1> : <span>فضای یادگیری شما</span>}</div><div className="header-actions"><LearnerMemory profile={profile} disabled={busy} onCorrect={correctTopic} onReset={resetProfile}/><span className="header-note">با سرعت خودتان یاد بگیرید</span><Button variant="ghost" size="icon" aria-label={dark ? "حالت روشن" : "حالت تیره"} onClick={() => setDark(!dark)}>{dark ? <Sun/> : <Moon/>}</Button></div></header>
      <div className="lesson-settings">
        <Select value={chat?.manualLevel || (topicEntry(profile,chat?.topic)?.level_source==="manual" ? topicEntry(profile,chat?.topic)!.level : "auto")} onValueChange={v => changeSetting("level",v)} disabled={busy}><SelectTrigger aria-label="سطح یادگیری"><SelectValue/></SelectTrigger><SelectContent><SelectGroup><SelectItem value="auto">خودکار</SelectItem>{Object.entries(levels).map(([value,label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectGroup></SelectContent></Select>
        <ToggleGroup dir="rtl" type="single" variant="outline" value={chat?.delivery || "step"} onValueChange={v => changeSetting("delivery",v)} disabled={busy || paused} aria-label="روش آموزش"><ToggleGroupItem value="step">قدم‌به‌قدم</ToggleGroupItem><ToggleGroupItem value="full">توضیح کامل</ToggleGroupItem></ToggleGroup>
        <Select value={chat?.mode || "learn"} onValueChange={v => changeSetting("mode",v)} disabled={busy || paused}><SelectTrigger aria-label="نوع پاسخ"><SelectValue/></SelectTrigger><SelectContent><SelectGroup><SelectItem value="learn">یادگیری</SelectItem><SelectItem value="answer">پاسخ کوتاه</SelectItem></SelectGroup></SelectContent></Select>
      </div>
      {chat?.topic && <p className="learner-level-status" role="status">سطح این موضوع: {levels[chat.level]} · {chat.levelSource==="manual" ? "انتخاب شما" : chat.levelSource==="inferred" ? "برآورد تقریبی؛ قابل اصلاح" : "پیش‌فرض"}</p>}
      {storageError && <Alert className="notice" variant="destructive"><AlertDescription>ذخیره‌سازی این مرورگر در دسترس نیست؛ برای نگه‌داشتن گفت‌وگوها خروجی بگیرید.</AlertDescription></Alert>}
      <ThreadViewport empty={!chat?.messages.length} key={chat?.id}>
        {!chat?.messages.length && <section className="welcome"><div className="welcome-symbol" aria-hidden="true"><Sigma/></div><h1>ریاضی، قدم به قدم.</h1><p>از هرجا که هستید شروع کنید.<br/>یک مفهوم را بفهمید، یک مسئله را حل کنید، یا دوباره بپرسید.</p><div className="suggestions">{suggestions.map(item => <button key={item.title} disabled={!loaded || busy} onClick={() => {setInput(item.query);inputRef.current?.focus();}}><span className="suggestion-icon"><Sparkles aria-hidden="true"/></span><strong>{item.title}</strong><span>{item.detail}</span><ChevronLeft aria-hidden="true"/></button>)}</div><span className="welcome-footnote">پرسش‌های فارسی و انگلیسی، هر دو پذیرفته می‌شوند.</span></section>}
        {chat?.messages.map(message => message.segments.length || message.blocks?.length ? message.role === "system" ? <p className="session-note" key={message.id}>{message.segments.map(s => s.text).join(" ")}</p> : <MessageRow from={message.role} key={message.id} className="lesson-message"><div className="message-label">{message.role === "user" ? "شما" : "هم‌درس"}{message.partial && <span>در حال دریافت</span>}</div><MessageContent className={message.blocks?.length ? "w-full" : undefined}>{message.segments.filter(Boolean).map((segment,index) => <MathText key={index} text={segment.text}/>)}{message.role==="assistant" && message.blocks?.map(block=><BlockRenderer key={block.id} entry={block} threadId={chat.threadId} disabled={busy || !!chat.expired || !!chat.pending || !chat.lesson?.awaiting_user} onChange={state=>changeBlock(message.id,block.id,state)} onAsk={askFromBlock} onEvent={eventFromBlock} onLocalEvent={localFromBlock}/>)}</MessageContent></MessageRow> : null)}
        {busy && <div className="writing" role="status"><span className="writing-dot"/>{phases[phase] || "در حال آماده‌سازی پاسخ…"}</div>}
      </ThreadViewport>
      <div className="composer-region">
        {degraded&&!busy&&<Alert className="notice"><AlertDescription>این پاسخ با امکانات محدود آماده شد؛ می‌توانید درس را ادامه بدهید.</AlertDescription></Alert>}
        {chat?.expired && <Alert className="notice"><AlertDescription>جلسهٔ قبلی دیگر روی سرور نیست. متن گفت‌وگو محفوظ است.<Button variant="outline" onClick={recover} disabled={busy}>ادامه در جلسهٔ تازه</Button></AlertDescription></Alert>}
        {error && <Alert className="notice" variant="destructive"><AlertDescription>{error}{chat?.pending && <Button variant="outline" disabled={busy} onClick={() => void send(chat.pending!.request.action,chat.pending!.request.message,chat.pending)}><RotateCcw data-icon="inline-start"/>تلاش دوباره</Button>}</AlertDescription></Alert>}
        {!error && !busy && chat?.pending && <Alert className="notice"><AlertDescription>یک پاسخ ناتمام ذخیره شده است.<Button variant="outline" onClick={() => void send(chat.pending!.request.action,chat.pending!.request.message,chat.pending)}>دریافت ادامهٔ پاسخ</Button></AlertDescription></Alert>}
        {paused && !chat?.expired && <div className="step-controls" role="group" aria-label="کنترل درس"><span>{chat?.lesson?.total_steps ? `گام ${faNumber(chat.lesson.step_index+1)} از ${faNumber(chat.lesson.total_steps)}` : "پرسش دیگری دارید؟"}</span><Button disabled={busy || !chat?.lesson?.can_continue} onClick={() => void send("next")}><ChevronLeft data-icon="inline-start"/>ادامه</Button><Button variant="outline" disabled={busy} onClick={() => void send("simplify")}>متوجه نشدم</Button><Button variant="outline" disabled={busy} onClick={() => void send("full")}>توضیح کامل</Button><Button variant="ghost" disabled={busy} onClick={() => void send("done")}><Check data-icon="inline-start"/>پایان درس</Button></div>}
        <form className="composer" onSubmit={e => {e.preventDefault();void send(paused ? "followup" : "new_lesson",input);}}><Field><FieldLabel htmlFor="prompt" className="sr-only">پرسش شما</FieldLabel><Textarea id="prompt" ref={inputRef} dir="auto" placeholder={paused ? "اینجا بیشتر بپرسید…" : "چه چیزی را می‌خواهید یاد بگیرید؟"} value={input} maxLength={8000} disabled={busy || !loaded || chat?.expired} onChange={e => setInput(e.target.value)} onKeyDown={e => {if(e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing){e.preventDefault();void send(paused ? "followup" : "new_lesson",input);}}}/></Field><div className="composer-bottom">{busy ? <Button type="button" size="icon" aria-label="توقف دریافت" onClick={() => controller.current?.abort()}><Square/></Button> : <Button type="submit" size="icon" aria-label="ارسال پرسش" disabled={!input.trim() || !loaded || chat?.expired}><ArrowUp/></Button>}</div></form>
        <p className="composer-hint">Enter برای ارسال · Shift + Enter برای خط تازه</p>
        {!chat?.messages.length && <p className="composer-caption">یادگیری با پرسیدن شروع می‌شود. برای نتیجه‌های مهم، راه‌حل را هم بررسی کنید.</p>}
      </div>
    </main>
    <Dialog open={!!editing} onOpenChange={open => !open && setEditing(null)}><DialogContent dir="rtl"><DialogHeader><DialogTitle>نام گفت‌وگو</DialogTitle></DialogHeader><Field><FieldLabel htmlFor="chat-name">نام تازه</FieldLabel><Input id="chat-name" value={rename} maxLength={80} onChange={e => setRename(e.target.value)}/></Field><DialogFooter><Button disabled={!rename.trim()} onClick={() => {if(editing) update(editing.id,old => ({...old,title: rename.trim()}));setEditing(null);}}>ذخیره نام</Button></DialogFooter></DialogContent></Dialog>
    <Dialog open={!!deleting} onOpenChange={open => !open && setDeleting(null)}><DialogContent dir="rtl"><DialogHeader><DialogTitle>حذف گفت‌وگو؟</DialogTitle></DialogHeader><p>«{deleting?.title}» از این دستگاه حذف می‌شود.</p><DialogFooter><Button variant="outline" onClick={() => setDeleting(null)}>انصراف</Button><Button variant="destructive" onClick={async () => {if(!deleting) return;try {await deleteChat(deleting.id);const rest = chats.filter(c => c.id !== deleting.id);setChats(rest);if(active === deleting.id){if(rest.length)setActive(rest[0].id);else {const fresh = newChat();setChats([fresh]);setActive(fresh.id);}}setDeleting(null);}catch{setStorageError(true);}}}>حذف گفت‌وگو</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}
