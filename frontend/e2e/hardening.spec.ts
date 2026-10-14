import {test,expect,type Page} from "@playwright/test";
import {spawn,spawnSync} from "node:child_process";
import path from "node:path";

const fixture="http://127.0.0.1:8766";
async function state(){const response=await fetch(`${fixture}/__qa/state`);const data=await response.json();if(data.fixture!=="w9")throw Error("A dedicated W9 fixture is required");return data;}
async function fault(kind:string){await state();const response=await fetch(`${fixture}/__qa/fault`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({kind})});expect(response.ok).toBe(true);}
async function ask(page:Page,text:string){
 await page.getByRole("textbox",{name:"پرسش شما"}).fill(text);
 const response=page.waitForResponse(r=>r.url().endsWith("/api/chat/stream"));
 await page.getByRole("button",{name:"ارسال پرسش",exact:true}).click();
 const body=await(await response).text();
 await expect(page.getByRole("button",{name:"توقف دریافت",exact:true})).toHaveCount(0,{timeout:130000});
 return body;
}
async function stopFixture(){const {pid}=await state();if(!Number.isInteger(pid))throw Error("Invalid owned fixture PID");if(process.platform==="win32")spawnSync("taskkill",["/PID",String(pid),"/T","/F"]);else process.kill(pid,"SIGTERM");}
async function restartFixture(){
 const root=path.resolve("..");const python=process.env.TUTOR_ACCEPTANCE_PYTHON||path.join(root,".venv",process.platform==="win32"?"Scripts/python.exe":"bin/python");
 const child=spawn(python,["scripts/serve_w9_fixture.py"],{cwd:root,stdio:"ignore",windowsHide:true,env:{...process.env,LANGSMITH_TRACING:"false",LANGCHAIN_TRACING_V2:"false"}});child.unref();
 await expect.poll(async()=>{try{return (await state()).fixture;}catch{return null;}},{timeout:90000}).toBe("w9");
}
test.beforeEach(async({browser},testInfo)=>{testInfo.annotations.push({type:'browser_version',description:browser.version()});await fault("none");});
test.afterEach(async()=>{try{await fault("none");}catch{}});

test("answer mode and an initially full lesson use the real graph and expose usage",async({page})=>{
 const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));await page.goto("/");
 await page.getByRole("combobox",{name:"نوع پاسخ"}).click();await page.getByRole("option",{name:"پاسخ کوتاه",exact:true}).click();
 const answer=await ask(page,"2x+5=17");expect(answer).toContain('"mode": "answer"');
 await expect(page.locator(".lesson-message").last()).toContainText("6");await expect(page.locator(".step-reveal")).toHaveCount(0);
 await page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true}).click();
 await page.getByRole("radio",{name:"توضیح کامل",exact:true}).click();
 const full=await ask(page,"لگاریتم را توضیح بده");expect(full).toContain('"delivery": "full"');expect(full).toContain('"prompt_tokens": 30');
 await expect(page.locator(".function-graph")).toHaveCount(1);await expect(page.locator(".step-reveal")).toHaveCount(1);
 await expect(page.locator(".katex-error")).toHaveCount(0);expect(errors).toEqual([]);
});

test("provider failures and invalid component proposals retain usable Persian text",async({page})=>{
 test.setTimeout(360000);const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));await page.goto("/");
 for(const kind of ["model_timeout","search_failure","embedding_failure","invalid_ui"]){
  await fault(kind);await page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true}).click();
  const body=await ask(page,"لگاریتم را توضیح بده");expect(body).not.toContain("PRIVATE_SERVICE_FAILURE");
  await expect(page.locator(".lesson-message").last()).toContainText(/[\u0600-\u06ff]/);
  if(kind!=="invalid_ui")await expect(page.getByText("این پاسخ با امکانات محدود آماده شد؛ می‌توانید درس را ادامه بدهید.",{exact:true})).toBeVisible();
  await expect(page.locator(".katex-error")).toHaveCount(0);
 }
 expect(errors).toEqual([]);
});

test("literal server restarts preserve paused and in-flight lessons in browser history",async({page})=>{
 test.setTimeout(360000);await page.goto("/");await ask(page,"لگاریتم را توضیح بده");
 await stopFixture();await restartFixture();await page.getByRole("button",{name:"ادامه",exact:true}).click();
 await expect(page.getByRole("button",{name:"ادامه در جلسهٔ تازه"})).toBeVisible();
 await page.getByRole("button",{name:"ادامه در جلسهٔ تازه"}).click();
 await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled({timeout:130000});
 await expect(page.getByText("ادامهٔ گفت‌وگو در یک جلسهٔ تازه",{exact:true})).toHaveCount(1);
 await fault("slow");await page.getByRole("textbox",{name:"پرسش شما"}).fill("این مفهوم را دوباره توضیح بده");await page.getByRole("button",{name:"ارسال پرسش",exact:true}).click();
 await expect.poll(async()=>(await state()).active_threads,{timeout:30000}).toBe(1);
 await stopFixture();await expect(page.getByRole("button",{name:"تلاش دوباره",exact:true})).toBeVisible({timeout:130000});
 await restartFixture();await page.getByRole("button",{name:"تلاش دوباره",exact:true}).click();
 await expect(page.getByRole("button",{name:"ادامه در جلسهٔ تازه"})).toBeVisible();
 await expect(page.getByText("این مفهوم را دوباره توضیح بده",{exact:true})).toBeVisible();
 await page.getByRole("button",{name:"ادامه در جلسهٔ تازه"}).click();
 await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled({timeout:130000});
 await expect(page.getByText("ادامهٔ گفت‌وگو در یک جلسهٔ تازه",{exact:true})).toHaveCount(2);
});
