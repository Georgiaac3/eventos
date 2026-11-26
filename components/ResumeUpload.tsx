"use client";

import { useRef, useState } from "react";
import { RESUME_EXTENSIONS, RESUME_MAX_BYTES, type Resume, api, uploadResume } from "@/lib/api";

const ACCEPT = [...RESUME_EXTENSIONS, "application/pdf", "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"].join(",");

function fmtSize(n: number) {
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

const ext = (name: string) => name.slice(name.lastIndexOf(".")).toLowerCase();

/** Resume picker for onboarding and settings. Uploads as soon as a file is chosen, independent of the form's Save. */
export function ResumeUpload({ initial }: { initial: Resume | null }) {
  const input = useRef<HTMLInputElement>(null);
  const [resume, setResume] = useState<Resume | null>(initial);
  const [busy, setBusy] = useState<string | null>(null); // "Uploading x.pdf…" / "Removing…"
  const [over, setOver] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function upload(file: File | undefined) {
    if (!file) return;
    setErr(null);
    if (!RESUME_EXTENSIONS.includes(ext(file.name))) return setErr("Upload a PDF or Word file (.pdf, .doc or .docx).");
    if (file.size > RESUME_MAX_BYTES) return setErr("That file is over 4 MB. Try exporting a smaller PDF.");
    setBusy(`Uploading ${file.name}…`);
    try {
      setResume(await uploadResume(file));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
      if (input.current) input.current.value = ""; // so picking the same file again still fires onChange
    }
  }

  async function remove() {
    setErr(null);
    setBusy("Removing…");
    try {
      await api("resume/delete", {});
      setResume(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const pick = () => input.current?.click();

  return (
    <div className="resume">
      <input ref={input} type="file" accept={ACCEPT} hidden onChange={(e) => upload(e.target.files?.[0])} />

      {resume ? (
        <div className="file-card">
          <span className="file-badge">{ext(resume.filename).slice(1).toUpperCase()}</span>
          <div className="file-info">
            <div className="file-name" title={resume.filename}>{resume.filename}</div>
            <div className="small muted">{busy ?? `${fmtSize(resume.size)} · Uploaded ${fmtDate(resume.uploadedAt)}`}</div>
          </div>
          <div className="file-actions">
            <button type="button" className="link" onClick={pick} disabled={!!busy}>Replace</button>
            <button type="button" className="link" onClick={remove} disabled={!!busy}>Remove</button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className={`dropzone ${over ? "over" : ""}`}
          onClick={pick}
          disabled={!!busy}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files[0]); }}
        >
          {busy ?? <><span><strong>Drop your resume here</strong> or browse</span><span className="small">PDF or Word · up to 4 MB</span></>}
        </button>
      )}

      {err && <p className="err" role="alert" style={{ margin: "8px 0 0" }}>{err}</p>}
    </div>
  );
}
