import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TutorShell } from "@/components/tutor-shell";
import { MathText } from "@/components/math-text";
import { newChat } from "@/lib/contracts";
import { loadChats, saveChat, deleteChat } from "@/lib/storage";
afterEach(cleanup);
describe("study shell",() => {
  it("shows an accessible Persian workspace and fills a starter question", async () => {
    render(<TutorShell/>);
    await waitFor(() => expect(screen.getByRole("button",{name:/^گفت‌وگوی تازه$/})).toBeEnabled());
    expect(screen.getByRole("heading",{name:"ریاضی، قدم به قدم."})).toBeVisible();
    fireEvent.click(screen.getByRole("button",{name:/لگاریتم را بفهمم/}));
    expect(screen.getByRole("textbox",{name:"پرسش شما"})).toHaveValue("لگاریتم را از ابتدا به من توضیح بده");
    expect(screen.getByRole("button",{name:"ارسال پرسش"})).toBeEnabled();
    fireEvent.click(screen.getByRole("button",{name:"حالت تیره"}));
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
  it("persists and deletes full transcripts with the versioned database",async () => {
    const chat=newChat();chat.title="Saved lesson";chat.messages=[{id:"one",role:"user",segments:[{kind:"text",text:"Explain logarithms"}]}];
    await saveChat(chat);
    expect((await loadChats()).find(row=>row.id===chat.id)?.messages[0].segments[0].text).toBe("Explain logarithms");
    await deleteChat(chat.id);
    expect((await loadChats()).some(row=>row.id===chat.id)).toBe(false);
  });
  it("renders mixed text and isolated math without executing supplied HTML",() => {
    const {container}=render(<MathText text={String.raw`تابع \(x^2\) و English. <script>alert(1)</script>`}/>);
    expect(container.querySelector(".katex")).not.toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("[dir=auto]")).not.toBeNull();
  });
  it("keeps Persian prose digits but uses Latin digits within math",() => {
    const {container}=render(<MathText text={String.raw`گام ۲: \(x^۲ + ۳\)`}/>);
    expect(container.textContent).toContain("گام ۲");
    expect(container.querySelector(".katex")?.textContent).toContain("3");
    expect(container.querySelector(".katex")?.textContent).not.toContain("۳");
  });
});
