// Agent-operated visual/keyboard checklist on Windows, with the offline fixture.
import { chromium, firefox } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
const destination=path.resolve("../.cache/w4-browser-review");
await fs.mkdir(destination,{recursive:true});
const observations=[];
for(const [name,engine] of [["chromium",chromium],["firefox",firefox]]) {
  const browser=await engine.launch(name==="chromium"?{channel:"chrome"}:{});
  const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:"reduce"});
  const errors=[];page.on("pageerror",error=>errors.push(error.message));
  await page.goto("http://127.0.0.1:3000/");
  await page.getByRole("button",{name:"گفت‌وگوی تازه",exact:true}).waitFor();
  await page.keyboard.press("Tab");
  const focus=await page.evaluate(()=>document.activeElement?.textContent);
  await page.screenshot({path:path.join(destination,`${name}-light.png`)});
  await page.getByRole("button",{name:"حالت تیره"}).click();
  await page.screenshot({path:path.join(destination,`${name}-dark.png`)});
  await page.setViewportSize({width:375,height:812});
  await page.getByRole("button",{name:"نمایش فهرست"}).click();
  await page.screenshot({path:path.join(destination,`${name}-mobile.png`)});
  await page.getByRole("button",{name:"بستن فهرست",exact:true}).first().click();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  observations.push({browser:name,version:browser.version(),os:"Windows",keyboardFirstFocus:focus,horizontalOverflowAt375:overflow,pageErrors:errors,reducedMotion:true,screenshots:[`${name}-light.png`,`${name}-dark.png`,`${name}-mobile.png`]});
  await browser.close();
}
await fs.writeFile(path.resolve("../sources/manifests/phase_w4_browser_review.json"),JSON.stringify({kind:"agent-operated visual/keyboard checklist; not a human sign-off",observations},null,2));
console.log(JSON.stringify(observations,null,2));
