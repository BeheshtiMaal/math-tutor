import { test, expect } from "@playwright/test";
test("real graph streaming, resume, reload, rename, export and delete",async ({page}) => {
  const runtimeErrors:string[]=[];page.on("pageerror",e=>runtimeErrors.push(e.message));
  await page.goto("/");
  await expect(page.getByRole("heading",{name:"ریاضی، قدم به قدم."})).toBeVisible();
  await expect(page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true})).toBeEnabled({timeout:30000});
  await page.getByRole("textbox",{name:"پرسش شما"}).fill("مفهوم مشتق را توضیح بده");
  await page.getByRole("button",{name:"ارسال پرسش"}).click();
  await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled();
  await expect(page.locator(".katex").first()).toBeVisible();
  const stepOne=await page.locator(".step-controls").innerText();expect(stepOne).toContain("۱");
  await page.getByRole("button",{name:"ادامه",exact:true}).click();
  await expect(page.locator(".step-controls")).toContainText("گام ۲");
  await expect(page.getByText("در توان n ضرب کن.",{exact:false})).toBeVisible();
  await page.waitForTimeout(400);await page.reload();
  await expect(page.locator(".step-controls")).toContainText("گام ۲");
  await expect(page.locator(".lesson-message")).toHaveCount(3);
  await page.getByRole("button",{name:"حالت تیره"}).click();await expect(page.locator("html")).toHaveAttribute("data-theme","dark");
  await page.getByRole("button",{name:"تغییر نام مفهوم مشتق را توضیح بده"}).click();
  await page.getByRole("textbox",{name:"نام تازه"}).fill("درس مشتق من");await page.getByRole("button",{name:"ذخیره نام"}).click();
  await page.getByRole("textbox",{name:"جست‌وجوی گفت‌وگوها"}).fill("درس مشتق من");await expect(page.getByRole("button",{name:"باز کردن درس مشتق من",exact:true})).toBeVisible();
  const download=page.waitForEvent("download");await page.getByRole("button",{name:"خروجی گفت‌وگوها"}).click();expect((await download).suggestedFilename()).toBe("mathtutor-chats.json");
  await page.getByRole("textbox",{name:"جست‌وجوی گفت‌وگوها"}).fill("");
  for(let i=0;i<2;i++){await page.getByRole("button",{name:"ادامه",exact:true}).click();await expect(page.getByRole("button",{name:"توقف دریافت"})).not.toBeVisible();}
  await page.getByRole("button",{name:"پایان درس"}).click();await expect(page.locator(".step-controls")).not.toBeVisible();
  await page.getByRole("button",{name:"حذف درس مشتق من"}).click();await page.getByRole("dialog").getByRole("button",{name:"حذف گفت‌وگو"}).click();
  await page.waitForTimeout(400);await page.reload();await expect(page.getByRole("button",{name:"باز کردن درس مشتق من",exact:true})).not.toBeVisible();expect(runtimeErrors).toEqual([]);
});

test("interrupted stream retries the same graph turn without duplicates",async ({page}) => {
  await page.goto("/");
  await expect(page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true})).toBeEnabled({timeout:30000});
  let dropped=false;
  await page.route("**/api/chat/stream",async route => {
    if(dropped) {await route.continue();return;}
    dropped=true;
    const response=await route.fetch();
    const text=await response.text();
    await route.fulfill({response,body:text.slice(0,text.lastIndexOf("event: turn_end"))});
  });
  await page.getByRole("textbox",{name:"پرسش شما"}).fill("Explain derivatives");
  await page.getByRole("button",{name:"ارسال پرسش"}).click();
  await expect(page.getByRole("button",{name:"تلاش دوباره"})).toBeVisible({timeout:30000});
  await page.getByRole("button",{name:"تلاش دوباره"}).click();
  await expect(page.locator(".step-controls")).toContainText("گام ۱");
  await expect(page.locator(".lesson-message")).toHaveCount(2);
});

test("unknown server thread preserves transcript and starts a labelled new session",async ({page}) => {
  await page.goto("/");
  await expect(page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true})).toBeEnabled({timeout:30000});
  await page.evaluate(async () => {
    const db=await new Promise<IDBDatabase>((resolve,reject)=>{const r=indexedDB.open("mathtutor",1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
    const transaction=db.transaction(["chats","settings"],"readwrite");
    const chat={id:"expired-example",threadId:"thr_00000000000000000000000000",title:"درس ذخیره‌شده",updatedAt:Date.now(),messages:[{id:"history",role:"user",segments:[{kind:"text",text:"مفهوم مشتق را توضیح بده"}]}],level:"beginner",delivery:"step",mode:"learn",lesson:{step_index:0,total_steps:4,awaiting_user:true,can_continue:true},topic:"derivative"};
    transaction.objectStore("chats").put(chat);transaction.objectStore("settings").put(chat.id,"active");
    await new Promise<void>(resolve=>transaction.oncomplete=()=>resolve());db.close();
  });
  await page.reload();
  await page.getByRole("button",{name:"باز کردن درس ذخیره‌شده",exact:true}).click();
  await page.getByRole("button",{name:"ادامه",exact:true}).click();
  await expect(page.getByRole("button",{name:"ادامه در جلسهٔ تازه"})).toBeVisible();
  await expect(page.getByText("مفهوم مشتق را توضیح بده",{exact:true}).last()).toBeVisible();
  await page.getByRole("button",{name:"ادامه در جلسهٔ تازه"}).click();
  await expect(page.getByText("ادامهٔ گفت‌وگو در یک جلسهٔ تازه",{exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled();
});
