/**
 * Tiny Markdown renderer for agent replies: paragraphs, "-"/"*"/"1." lists, **bold**, *italic*,
 * `code`, [text](url) and bare URLs. Builds React elements (no innerHTML), so replies can't inject markup.
 */
import { Fragment, type ReactNode } from "react";

const INLINE = /(\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)\s]+\)|https?:\/\/[^\s)]+|`[^`]+`|\*[^*\s][^*]*\*)/g;

function inline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{inline(part.slice(2, -2))}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i}>{part.slice(1, -1)}</code>;
    const link = part.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/);
    if (link) return <a key={i} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a>;
    if (/^https?:\/\//.test(part)) {
      const url = part.replace(/[.,;:!?]+$/, "");
      const label = url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");
      return <Fragment key={i}><a href={url} target="_blank" rel="noreferrer">{label.length > 48 ? label.slice(0, 45) + "…" : label}</a>{part.slice(url.length)}</Fragment>;
    }
    if (part.length > 2 && part.startsWith("*") && part.endsWith("*")) return <em key={i}>{part.slice(1, -1)}</em>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let para: string[] = [];

  const flushPara = () => {
    if (para.length) blocks.push(<p key={blocks.length}>{inline(para.join(" "))}</p>);
    para = [];
  };
  const flushList = () => {
    if (!list) return;
    const items = list.items.map((it, i) => <li key={i}>{inline(it)}</li>);
    blocks.push(list.ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>);
    list = null;
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const bullet = line.match(/^[-*•]\s+(.*)$/);
    const num = line.match(/^\d+[.)]\s+(.*)$/);
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    if (bullet || num) {
      flushPara();
      const ordered = !!num;
      if (list && list.ordered !== ordered) flushList();
      if (!list) list = { ordered, items: [] };
      list.items.push((bullet ?? num)![1]);
    } else if (!line) {
      flushPara();
      flushList();
    } else if (heading) {
      flushPara();
      flushList();
      blocks.push(<p key={blocks.length}><strong>{inline(heading[1])}</strong></p>);
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return <div className="md">{blocks}</div>;
}
