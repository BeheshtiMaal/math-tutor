import {test,expect,type Page} from "@playwright/test";

async function ask(page:Page,text:string){
  await page.getByRole("textbox",{name:"پرسش شما"}).fill(text);
  await page.getByRole("button",{name:"ارسال پرسش",exact:true}).click();
  await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled({timeout:130000});
}
async function profile(page:Page){return page.evaluate(async()=>{
  const db=await new Promise<IDBDatabase>((resolve,reject)=>{const request=indexedDB.open("mathtutor",1);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
  try{return await new Promise<any>((resolve,reject)=>{const request=db.transaction("settings","readonly").objectStore("settings").get("learner-profile");request.onsuccess=()=>resolve(JSON.parse(request.result||"null"));request.onerror=()=>reject(request.error);});}finally{db.close();}
});}

test("memory records confusion, adapts the next lesson, retains corrections and resets locally",async({page})=>{
  test.setTimeout(360000);
  const requests:any[]=[],errors:string[]=[];
  page.on("request",request=>{if(request.url().endsWith("/api/chat/stream"))requests.push(request.postDataJSON());});
  page.on("pageerror",error=>errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("combobox",{name:"سطح یادگیری"})).toContainText("خودکار");
  await ask(page,"لگاریتم را از صفر توضیح بده");
  expect(requests[0]).not.toHaveProperty("level");expect(requests[0].level_source).toBe("inferred");
  await expect(page.locator(".learner-level-status")).toContainText("مبتدی");
  await page.getByRole("button",{name:"متوجه نشدم",exact:true}).click();
  await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled();
  expect((await profile(page)).topics.logarithms.confusion_spots[0].count).toBe(1);
  await page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true}).click();
  await ask(page,"لگاریتم را توضیح بده");
  await expect(page.locator(".lesson-message").last()).toContainText("ابتدا شرط پایه را مرور کنیم");
  expect(requests[2].learner_profile.topics.logarithms.confusion_spots).toHaveLength(1);
  await ask(page,"یک مثال از لگاریتم بده");
  const reveal=page.locator(".step-reveal");
  await reveal.getByRole("button",{name:"مرحلهٔ بعد"}).click();
  await reveal.getByRole("button",{name:"این مرحله را نفهمیدم"}).click();
  await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled();
  const memory=await profile(page);expect(memory.topics.logarithms.confusion_spots).toHaveLength(2);
  await page.getByRole("button",{name:"حافظه یادگیری",exact:true}).click();
  const dialog=page.getByRole("dialog");
  await expect(dialog).toContainText("آزمون مهارت نیست");
  await dialog.getByRole("combobox",{name:"سطح لگاریتم"}).click();
  await page.getByRole("option",{name:"پیشرفته",exact:true}).click();
  await expect(dialog.getByText("انتخاب شما",{exact:true})).toBeVisible();
  await dialog.getByRole("button",{name:"بستن",exact:true}).click();
  await page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true}).click();
  await ask(page,"لگاریتم را از صفر توضیح بده");
  await expect(page.locator(".learner-level-status")).toContainText("پیشرفته");
  await expect(page.locator(".learner-level-status")).toContainText("انتخاب شما");
  await page.reload();
  expect((await profile(page)).topics.logarithms.level_source).toBe("manual");
  await page.getByRole("button",{name:"حافظه یادگیری",exact:true}).click();
  await dialog.getByRole("button",{name:"پاک کردن حافظه",exact:true}).click();
  await expect(dialog.getByRole("status")).toContainText("حافظه پاک شد");
  expect((await profile(page)).topics).toEqual({});
  await expect(dialog).toContainText("۰ موضوع ذخیره‌شده");
  await dialog.getByRole("button",{name:"بستن",exact:true}).click();
  await expect(page.locator(".lesson-message")).not.toHaveCount(0);
  await page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true}).click();
  await ask(page,"لگاریتم را از صفر توضیح بده");
  const request=requests.at(-1);expect(request.learner_profile.topics).toEqual({});
  await expect(page.locator(".learner-level-status")).toContainText("مبتدی");
  await expect(page.locator(".katex-error")).toHaveCount(0);expect(errors).toEqual([]);
});

test("a fluent question selects deeper teaching without manual settings",async({page})=>{
  await page.goto("/");
  await ask(page,"رابطه تغییر پایه لگاریتم را با یک به یک بودن تابع نمایی اثبات کن");
  await expect(page.locator(".learner-level-status")).toContainText("پیشرفته");
  await expect(page.locator(".learner-level-status")).toContainText("برآورد تقریبی");
  await expect(page.locator(".lesson-message").last()).toContainText("برای اثبات رابطه");
  await expect(page.getByRole("combobox",{name:"سطح یادگیری"})).toContainText("خودکار");
  const stored=await profile(page);expect(stored.topics.logarithms.level).toBe("advanced");
});
