import { test, expect } from "@playwright/test";

async function logarithmLesson(page: import("@playwright/test").Page, theme:"light"|"dark"="light") {
  await page.goto("/");
  await expect(page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true})).toBeEnabled();
  if(theme==="dark") await page.getByRole("button",{name:"حالت تیره"}).click();
  await page.getByRole("textbox",{name:"پرسش شما"}).fill("لگاریتم را از ابتدا توضیح بده");
  await page.getByRole("button",{name:"ارسال پرسش"}).click();
  await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled({timeout:130000});
}

for(const theme of ["light","dark"] as const) test(`logarithm components, keyboard and persistence in ${theme}`,async({page})=>{
  const errors:string[]=[], chatRequests:string[]=[], sampleValues:number[]=[];
  page.on("pageerror",error=>errors.push(error.message));
  page.on("request",request=>{if(request.url().endsWith("/api/chat/stream"))chatRequests.push(request.url());if(request.url().endsWith("/api/ui/sample"))sampleValues.push(request.postDataJSON().parameters.b);});
  await page.emulateMedia({reducedMotion:"reduce"});
  await logarithmLesson(page,theme);
  const graph=page.locator(".function-graph"), reveal=page.locator(".step-reveal"), slider=graph.getByRole("slider",{name:"پارامتر b"});
  await expect(graph.getByRole("img")).toBeVisible();
  await expect(slider).toHaveAttribute("aria-valuenow","2");
  await expect(graph.locator(".plot-gap")).toHaveCount(1);
  await expect(graph.locator(".graph-highlights")).toContainText("3");
  await slider.focus();await slider.press("Home");for(let i=0;i<4;i++)await slider.press("ArrowRight");
  await expect(slider).toHaveAttribute("aria-valuenow","0.5");
  await expect(graph.locator(".graph-highlights")).toContainText(/[-−]3/);
  await expect(graph.getByRole("img")).toBeVisible();
  expect(sampleValues.at(-1)).toBe(0.5);expect(chatRequests).toHaveLength(1);
  await expect(page.locator(".step-controls")).toContainText("گام ۱");
  await reveal.getByRole("button",{name:"مرحلهٔ بعد"}).click();
  await expect(reveal).toContainText("مرحلهٔ ۲ از ۳");
  await expect(reveal.locator(".changed-math").first()).toBeVisible();
  await reveal.getByRole("button",{name:"این مرحله را نفهمیدم"}).click();
  await expect(page.getByRole("button",{name:"ادامه",exact:true})).toBeEnabled();
  await expect(page.locator(".lesson-message")).toContainText([/این مرحله را ساده‌تر/]);
  expect(chatRequests).toHaveLength(2);
  await reveal.getByRole("button",{name:"مرحلهٔ بعد"}).click();await expect(reveal).toContainText("مرحلهٔ ۳ از ۳");
  await expect(reveal.getByRole("button",{name:"مرحلهٔ بعد"})).toBeDisabled();
  await expect(page.locator(".library-footer")).toContainText("گفت‌وگوها روی این دستگاه ذخیره می‌شوند");await page.reload();
  await expect(page.getByRole("slider",{name:"پارامتر b"})).toHaveAttribute("aria-valuenow","0.5");
  await expect(page.locator(".function-graph .graph-highlights")).toContainText(/[-−]3/);
  await expect(page.locator(".step-reveal")).toContainText("مرحلهٔ ۳ از ۳");
  await expect(page.locator("html")).toHaveAttribute("data-theme",theme);
  await page.locator(".step-reveal").getByRole("button",{name:"مرحلهٔ قبل"}).click();
  await expect(page.locator(".step-reveal")).toContainText("مرحلهٔ ۲ از ۳");
  expect(chatRequests).toHaveLength(2);expect(errors).toEqual([]);
});

test("invalid base and network failure hide stale curves and can recover",async({page})=>{
  await logarithmLesson(page);
  const graph=page.locator(".function-graph"), slider=graph.getByRole("slider",{name:"پارامتر b"});
  await slider.press("Home");for(let i=0;i<9;i++)await slider.press("ArrowRight");
  await expect(slider).toHaveAttribute("aria-valuenow","1");
  await expect(graph.getByText(/این مقادیر برای تابع تعریف نشده/)).toBeVisible();
  await expect(graph.getByRole("img")).not.toBeVisible();
  let fail=true;
  await page.route("**/api/ui/sample",async route=>{if(fail){await route.fulfill({status:502,contentType:"application/json",body:JSON.stringify({error:{code:"network_error"}})});}else await route.continue();});
  await slider.press("Home");for(let i=0;i<4;i++)await slider.press("ArrowRight");
  await expect(graph.getByText(/ارتباط با نمودار برقرار نشد/)).toBeVisible();
  fail=false;await graph.getByRole("button",{name:"تلاش دوباره برای نمودار"}).click();
  await expect(graph.locator(".graph-highlights")).toContainText(/[-−]3/);
});

test("unknown blocks degrade safely and unchecked steps stay labelled",async({page})=>{
  await page.route("**/api/chat/stream",async route=>{
    const response=await route.fetch();
    const body=(await response.text()).split("\n\n").map(frame=>{
      if(!frame.startsWith("event: block\n"))return frame;
      const data=JSON.parse(frame.slice(frame.indexOf("data: ")+6));
      if(data.block.type==="function_graph"){data.block.version=99;data.block.fallback_text="<script>window.untrustedBlock = true</script> این نمودار به صورت متن نمایش داده شد.";}
      else data.block.params.steps[1].verification="unknown";
      return `event: block\ndata: ${JSON.stringify(data)}`;
    }).join("\n\n");
    await route.fulfill({response,body});
  });
  await logarithmLesson(page);
  await expect(page.locator(".block-fallback")).toContainText("این نمودار به صورت متن نمایش داده شد.");
  expect(await page.evaluate(()=>Object.prototype.hasOwnProperty.call(window,"untrustedBlock"))).toBe(false);
  await page.locator(".step-reveal").getByRole("button",{name:"مرحلهٔ بعد"}).click();
  await expect(page.getByText("بررسی ماشینی نشده",{exact:true})).toBeVisible();
  await expect(page.locator(".step-controls")).toContainText("گام ۱");
});
