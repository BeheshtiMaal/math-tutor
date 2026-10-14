import {afterEach,expect,it} from "vitest";
import {cleanup,render} from "@testing-library/react";
import {MathText} from "@/components/math-text";
afterEach(cleanup);

it("renders an indented source align environment in display mode",()=>{
  const text=String.raw`مثال:

            \[\begin{align*}y^2 + 12y + 36 & = 0\\ (y+6)^2 & = 0\\ y & = -6\end{align*}\]

            \[y = -6\]`;
  const {container}=render(<MathText text={text}/>);
  expect(container.querySelector(".katex-error")).toBeNull();
  expect(container.querySelectorAll(".katex-display")).toHaveLength(2);
});

it("formats legacy plain polynomials and products in Persian lesson prose",()=>{
  const {container}=render(<MathText text="عبارت x^2 - 5*x + 6 به صورت (x - 2)*(x - 3) تجزیه می‌شود."/>);
  expect(container.querySelectorAll(".katex")).toHaveLength(2);
  expect(container.querySelector(".katex-error")).toBeNull();
  expect(container.textContent).toContain("تجزیه می‌شود");
});

it("preserves code, escaped currency, dates and ordinary Markdown",()=>{
  const {container}=render(<MathText text={String.raw`**یادداشت** در 2026-10-14 با قیمت \$5.

کد: \`x^2\` و \`\(x\)\`.

\`\`\`text
\[x^2\]
\`\`\``.replace(/\\`/g,"`")}/>);
  expect(container.querySelectorAll(".katex")).toHaveLength(0);
  expect(container.querySelector("strong")).toHaveTextContent("یادداشت");
  expect(container.textContent).toContain("2026-10-14");
});

it("keeps math digits Latin and prose digits Persian for both delimiter styles",()=>{
  const {container}=render(<MathText text={String.raw`گام ۲: \(x^۲ + ۳\) و $$x = ۳$$`}/>);
  expect(container.textContent).toContain("گام ۲");
  expect(container.querySelectorAll(".katex")).toHaveLength(2);
  for(const node of container.querySelectorAll(".katex"))expect(node.textContent).not.toMatch(/[۰-۹]/);
});

it("does not execute HTML or trust unsafe TeX links",()=>{
  const {container}=render(<MathText text={String.raw`<script>alert(1)</script> \(\href{javascript:alert(1)}{x}\)`}/>);
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
});
