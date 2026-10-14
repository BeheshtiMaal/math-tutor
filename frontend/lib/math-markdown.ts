// Normalize notation only. No expression evaluation or changes to saved text.
const digits=(text:string)=>text.replace(/[۰-۹٠-٩]/g,digit=>String(digit.charCodeAt(0)-(digit>="۰"?1776:1632)));
const atom=String.raw`(?:\b(?:log|ln|sin|cos|tan|exp|sqrt|abs)\([^()\n]{1,80}\)|\([A-Za-z0-9.+*/^=,\s-]{1,100}\)|pi|[A-Za-z](?:_[A-Za-z0-9])?|\d+(?:\.\d+)?)`;
const expression=new RegExp(String.raw`(?<![\w\\])${atom}(?:[ \t]*[=+*/^<>-][ \t]*${atom})+(?![\w])`,"g");

function legacyMath(text:string):string {
  // Incomplete streamed TeX remains intact until its closing delimiter arrives.
  const opening=text.search(/\\[[(]|(?<!\\)\$/);
  const prefix=opening<0?text:text.slice(0,opening),suffix=opening<0?"":text.slice(opening);
  return prefix.replace(expression,value=>{
    // Dates/ranges and prose punctuation are not inferred as arithmetic.
    if(!/[A-Za-z]/.test(value)&&!/[=*^/]/.test(value))return value;
    const latex=digits(value).replace(/\^\s*\(([^()]*)\)/g,(_,power)=>`^{${power}}`)
      .replace(/\^\s*(-?\d+(?:\.\d+)?|[A-Za-z])/g,(_,power)=>`^{${power}}`)
      .replace(/\bsqrt\(([^()]*)\)/g,(_,body)=>`\\sqrt{${body}}`)
      .replace(/\babs\(([^()]*)\)/g,(_,body)=>`\\lvert ${body}\\rvert`)
      .replace(/\blog\(([^(),]*),([^(),]*)\)/g,(_,body,base)=>`\\log_{${base}}(${body})`)
      .replace(/\b(log|ln|sin|cos|tan|exp)\(/g,(_,name)=>`\\${name}(`)
      .replace(/\bpi\b/g,"\\pi").replace(/\*/g,"\\cdot ");
    return `$${latex}$`;
  })+suffix;
}

export function mathMarkdown(text:string):string {
  // Protect code and URLs before interpreting math delimiters. Replacement
  // callbacks preserve literal $$; replacement strings treat $$ as a single $.
  const regions=/```[^\n]*\n[\s\S]*?```|~~~[^\n]*\n[\s\S]*?~~~|`+[^`\n]*`+|https?:\/\/[^\s]+|\\\[([\s\S]*?)\\\]|\$\$([\s\S]*?)\$\$|\\\(([\s\S]*?)\\\)|(?<![\\$])\$([^$\n]+?)(?<!\\)\$(?!\$)/g;
  let output="",cursor=0;
  for(const match of text.matchAll(regions)) {
    output+=legacyMath(text.slice(cursor,match.index));
    const display=match[1]??match[2],inline=match[3]??match[4];
    output+=display!==undefined ? `\n\n$$\n${digits(display).trim()}\n$$\n\n` : inline!==undefined ? `$${digits(inline).trim()}$` : match[0];
    cursor=match.index!+match[0].length;
  }
  return output+legacyMath(text.slice(cursor));
}
