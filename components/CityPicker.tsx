"use client";

import { useId, useRef, useState } from "react";
import { type CityPlatform, resolveCity, searchCities } from "@/lib/cities";

interface Props {
  platform: CityPlatform;
  /** Stored values: platform ids ("ma--boston"), or older free-text entries ("boston"). */
  value: string[];
  onChange: (value: string[]) => void;
  /** How many cities the connector actually searches; further picks are blocked. */
  max?: number;
  label: string;
}

/** Type-ahead, multi-select city dropdown. Emits each platform's own id for the city. */
export function CityPicker({ platform, value, onChange, max, label }: Props) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  // Older entries become proper ids; unknown ones are kept as typed so nothing is silently dropped.
  const selected = value.map((v) => {
    const c = resolveCity(platform, v);
    return { id: c?.[platform] ?? v, label: c?.label ?? v };
  });
  const chosen = new Set(selected.map((s) => s.id));
  const full = max !== undefined && selected.length >= max;
  const options = searchCities(platform, q).filter((c) => !chosen.has(c[platform]!)).slice(0, 50);

  const set = (ids: string[]) => onChange(ids);
  function add(cityId: string) {
    if (full) return;
    set([...selected.map((s) => s.id), cityId]);
    setQ("");
    setActive(0);
    input.current?.focus();
  }
  const remove = (cityId: string) => set(selected.filter((s) => s.id !== cityId).map((s) => s.id));

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setOpen(true);
      const n = options.length;
      if (n) setActive((a) => (a + (e.key === "ArrowDown" ? 1 : -1) + n) % n);
    } else if (e.key === "Enter") {
      e.preventDefault(); // don't submit anything
      if (open && options[active]) add(options[active][platform]!);
    } else if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "Backspace" && !q && selected.length) {
      remove(selected[selected.length - 1].id);
    }
  }

  const listId = `${id}-list`;
  const showList = open && !full;

  return (
    <div className="citypicker" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false); }}>
      <div className="citypicker-box" onClick={() => input.current?.focus()}>
        {selected.map((s) => (
          <span key={s.id} className="city-chip">
            {s.label}
            <button type="button" aria-label={`Remove ${s.label}`} onClick={(e) => { e.stopPropagation(); remove(s.id); }}>×</button>
          </span>
        ))}
        <input
          ref={input}
          role="combobox"
          aria-label={label}
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && options[active] ? `${id}-${active}` : undefined}
          value={q}
          placeholder={full ? "" : selected.length ? "Add another city" : "Type a city, e.g. Boston"}
          onChange={(e) => { setQ(e.target.value); setActive(0); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
          readOnly={full}
        />
      </div>

      {showList && (
        <ul id={listId} role="listbox" aria-label={`${label} suggestions`} className="citypicker-list">
          {options.length ? options.map((c, i) => (
            <li
              key={c[platform]}
              id={`${id}-${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? "active" : ""}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => e.preventDefault()} // keep focus in the input
              onClick={() => add(c[platform]!)}
            >
              {c.label}
            </li>
          )) : (
            <li className="none" aria-disabled="true">No match for “{q.trim()}”</li>
          )}
        </ul>
      )}
      {full && max !== undefined && max > 1 && <span className="small faint">Up to {max} cities. Remove one to pick another.</span>}
    </div>
  );
}
