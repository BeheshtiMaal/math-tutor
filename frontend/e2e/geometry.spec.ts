import {test,expect,type Page} from "@playwright/test";

async function connectFixture(page:Page){
  for(const path of ["/api/chat/stream","/api/ui/geometry"]){
    await page.route(`**${path}`,async route=>{
      const request=route.request();
      const response=await page.request.post(`http://127.0.0.1:8766${path}`,{data:request.postData(),headers:{"content-type":"application/json",...(request.headers()["x-request-id"]?{"x-request-id":request.headers()["x-request-id"]}:{})}});
      await route.fulfill({response});
    });
  }
}
async function lesson(page:Page,message:string){
  await page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true}).click();
  await page.getByRole("textbox",{name:"پرسش شما"}).fill(message);
  await page.getByRole("button",{name:"ارسال پرسش",exact:true}).click();
  await expect(page.locator(".geometry-canvas")).toHaveCount(1);
  await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled();
}

test("geometry scenes: keyboard, drag, reset, persistence, novelty and mobile themes",async({page},testInfo)=>{
  const errors:string[]=[],chatRequests:string[]=[],updates:string[]=[];
  page.on("pageerror",error=>errors.push(error.message));
  page.on("request",request=>{if(request.url().endsWith("/api/chat/stream"))chatRequests.push(request.url());if(request.url().endsWith("/api/ui/geometry"))updates.push(request.postData()||"");});
  await connectFixture(page);
  await page.goto("/");
  await page.emulateMedia({reducedMotion:"reduce"});
  await lesson(page,"دایره واحد را از ابتدا توضیح بده");
  const canvas=page.locator(".geometry-canvas");
  await expect(canvas.getByTestId("geometry-angle_deg")).toHaveText("45°");
  const point=canvas.getByRole("button",{name:"جابه‌جایی نقطه P"});
  await point.focus();await point.press("ArrowUp");
  await expect(canvas.getByTestId("geometry-angle_deg")).toHaveText("46°");
  expect(chatRequests).toHaveLength(1);
  await expect(page.locator(".library-footer [role=status]")).toHaveText("گفت‌وگوها روی این دستگاه ذخیره می‌شوند");
  await page.reload();
  await expect(canvas.getByTestId("geometry-angle_deg")).toHaveText("46°");
  expect(chatRequests).toHaveLength(1);
  await canvas.getByRole("button",{name:"بازنشانی شکل"}).click();
  await expect(canvas.getByTestId("geometry-angle_deg")).toHaveText("45°");
  const svg=canvas.locator(".geometry-plot");await svg.scrollIntoViewIfNeeded();
  await point.scrollIntoViewIfNeeded();
  const start=await point.locator(".geometry-hit").boundingBox(),box=await svg.boundingBox();expect(start).not.toBeNull();expect(box).not.toBeNull();
  await page.mouse.move(start!.x+start!.width/2,start!.y+start!.height/2);await page.mouse.down();
  await page.mouse.move(box!.x+box!.width/2,box!.y+box!.height*(86.46/560),{steps:8});await page.mouse.up();
  await expect(canvas.getByTestId("geometry-angle_deg")).toHaveText(/^(89|90|91)°$/);
  await page.getByRole("textbox",{name:"پرسش شما"}).fill("چرا شعاع ثابت است؟");await page.getByRole("button",{name:"ارسال پرسش",exact:true}).click();
  await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled();
  await expect(page.locator(".geometry-canvas")).toHaveCount(1);
  await lesson(page,"زاویه‌های مثلث را توضیح بده");
  await expect(canvas.getByTestId("geometry-area")).toHaveText("6");
  await canvas.getByRole("button",{name:"جابه‌جایی نقطه C"}).focus();
  await page.keyboard.press("ArrowRight");
  await expect(canvas.getByTestId("geometry-angle_A")).not.toHaveText("90°");
  await canvas.getByRole("button",{name:"بازنشانی شکل"}).click();
  await expect(canvas.getByTestId("geometry-angle_A")).toHaveText("90°");
  await lesson(page,"جمع بردارها را توضیح بده");
  await expect(canvas.getByTestId("geometry-length_sum")).toHaveText("5");
  await canvas.getByRole("button",{name:"جابه‌جایی نقطه u"}).focus();await page.keyboard.press("ArrowRight");
  await expect(canvas.getByTestId("geometry-length_sum")).not.toHaveText("5");
  await expect(page.locator(".katex-error")).toHaveCount(0);
  for(const theme of ["light","dark"]){
    if(theme==="dark")await page.getByRole("button",{name:"حالت تیره"}).click();
    await page.setViewportSize({width:375,height:812});
    await canvas.locator("h2").scrollIntoViewIfNeeded();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:`../.cache/geometry-${testInfo.project.name}-${theme}.png`});
  }
  expect(updates.length).toBeGreaterThanOrEqual(4);expect(errors).toEqual([]);
});
