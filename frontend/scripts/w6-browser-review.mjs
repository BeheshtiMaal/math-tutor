// Agent-operated W6 visual/keyboard checklist; real graph and SymPy fixture.
import {chromium,firefox} from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
const destination=path.resolve("../.cache/w6-browser-review");
await fs.mkdir(destination,{recursive:true});
const observations=[];
for(const [name,engine] of [["chromium",chromium],["firefox",firefox]]) {
  const browser=await engine.launch(name==="chromium" ? {channel:"chrome"}:{});
  try {
  const page=await browser.newPage({viewport:{width:1440,height:1200},reducedMotion:"reduce"});
  page.setDefaultTimeout(130000);
  const errors=[];page.on("pageerror",error=>errors.push(error.message));
  await page.goto("http://127.0.0.1:3000/");
  await page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true}).waitFor();
  await page.getByRole("textbox",{name:"پرسش شما"}).fill("لگاریتم را از ابتدا توضیح بده");
  await page.getByRole("button",{name:"ارسال پرسش"}).click();
  await page.getByRole("button",{name:"ادامه",exact:true}).waitFor();
  const slider=page.getByRole("slider",{name:"پارامتر b"});
  await slider.waitFor();await page.waitForFunction(()=>document.querySelector('[role=slider]')?.getAttribute('aria-disabled')!=='true');
  await page.locator(".function-graph").screenshot({path:path.join(destination,`${name}-graph-light.png`)});
  await slider.press("Home");for(let i=0;i<4;i++)await slider.press("ArrowRight");
  await page.waitForFunction(()=>document.querySelector('.graph-highlights')?.textContent?.includes('-3'));
  await page.locator(".step-reveal").getByRole("button",{name:"مرحلهٔ بعد"}).click();
  await page.getByRole("button",{name:"حالت تیره"}).click();
  await page.locator(".function-graph").screenshot({path:path.join(destination,`${name}-graph-dark.png`)});
  await page.locator(".step-reveal").screenshot({path:path.join(destination,`${name}-step-dark.png`)});
  const mathDirection=await page.locator('.katex').first().evaluate(node=>getComputedStyle(node).direction);
  const revealAnimation=await page.locator('.reveal-equations').evaluate(node=>getComputedStyle(node).animationName);
  await page.setViewportSize({width:375,height:812});
  await page.locator(".function-graph").scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(destination,`${name}-mobile-dark.png`)});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  observations.push({browser:name,version:browser.version(),os:"Windows",pageErrors:errors,horizontalOverflowAt375:overflow,
    mathDirection,reducedMotionAnimation:revealAnimation,sliderValue:await slider.getAttribute('aria-valuenow'),
    changedMathVisible:await page.locator('.changed-math').count()>0,screenshots:[`${name}-graph-light.png`,`${name}-graph-dark.png`,`${name}-step-dark.png`,`${name}-mobile-dark.png`]});
  } finally {await browser.close();}
}
await fs.writeFile(path.resolve("../sources/manifests/phase_w6_browser_review.json"),JSON.stringify({kind:"agent-operated Windows checklist; not human sign-off",observations},null,2));
console.log(JSON.stringify(observations,null,2));
