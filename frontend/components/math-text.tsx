"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import {mathMarkdown} from "@/lib/math-markdown";
export function MathText({text}: {text: string}) {
  const markdown = mathMarkdown(text);
  return <div className="math-text" dir="auto"><ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[[rehypeKatex, {throwOnError: false, strict: "ignore", trust: false}]]} skipHtml>{markdown}</ReactMarkdown></div>;
}
