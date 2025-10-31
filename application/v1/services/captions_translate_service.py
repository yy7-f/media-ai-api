import os, uuid, json, re, shutil
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from werkzeug.utils import secure_filename

# Argos Translate (offline)
import argostranslate.package as argos_package
import argostranslate.translate as argos_translate


@dataclass
class CaptionsTranslateResult:
    out_json: str
    out_srt: Optional[str]
    out_vtt: Optional[str]
    diagnostics: Dict


class CaptionsTranslateService:
    ALLOWED = {"srt", "vtt", "json"}

    @staticmethod
    def allowed_file(name: str) -> bool:
        return "." in name and name.rsplit(".", 1)[1].lower() in CaptionsTranslateService.ALLOWED

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not CaptionsTranslateService.allowed_file(name):
            raise ValueError("Unsupported file type. Upload .srt / .vtt / .json")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(path)
        return path

    def __init__(self, captions_path: str, work_root="uploads", output_root="captions_output"):
        if not os.path.isfile(captions_path):
            raise FileNotFoundError(captions_path)
        self.captions_path = captions_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(captions_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.out_json = os.path.join(self.output_root, f"{base}_translated_{self.session_id}.json")
        self.out_srt  = os.path.join(self.output_root, f"{base}_translated_{self.session_id}.srt")
        self.out_vtt  = os.path.join(self.output_root, f"{base}_translated_{self.session_id}.vtt")

    # ---------- Argos helpers ----------
    @staticmethod
    def _ensure_model(src: str, tgt: str):
        """
        Ensure Argos package for src->tgt is installed.
        Downloads from the default repo if missing.
        """
        available = argos_package.get_available_packages()
        installed = argos_package.get_installed_packages()

        def has_pair(pkgs):
            for p in pkgs:
                if p.from_code == src and p.to_code == tgt:
                    return p
            return None

        if has_pair(installed):
            return

        pkg = has_pair(available)
        if not pkg:
            # Try reverse? If still not, raise.
            raise RuntimeError(f"No Argos package found for {src}->{tgt}.")
        argos_package.install_from_path(pkg.download())

    @staticmethod
    def _get_translator(src: Optional[str], tgt: str):
        # If src is None, Argos will still translate but results improve with correct src.
        # We try to pick a pair that matches src if provided, else any that ends with ->tgt.
        translations = argos_translate.get_installed_languages()
        from_lang = None
        to_lang = None
        for lang in translations:
            if lang.code == tgt:
                to_lang = lang
            if src and lang.code == src:
                from_lang = lang

        if from_lang and to_lang:
            return from_lang.get_translation(to_lang)

        # fallback: pick first language that can translate to tgt
        if to_lang:
            for lang in translations:
                try:
                    tr = lang.get_translation(to_lang)
                    if tr:
                        return tr
                except Exception:
                    continue
        raise RuntimeError("No suitable Argos translator loaded")

    # ---------- format helpers ----------
    @staticmethod
    def _parse_srt(text: str) -> List[Dict]:
        entries = []
        # Blocks separated by blank lines, typical SRT format
        blocks = re.split(r"\n\s*\n", text.strip(), flags=re.MULTILINE)
        ts_re = re.compile(r"(\d\d:\d\d:\d\d[,\.]\d\d\d)\s*-->\s*(\d\d:\d\d:\d\d[,\.]\d\d\d)")
        def ts_to_sec(ts: str) -> float:
            ts = ts.replace(",", ".")
            h,m,s = ts.split(":")
            sec, ms = (s.split(".")+["0"])[:2]
            return int(h)*3600 + int(m)*60 + int(sec) + int(ms)/1000.0

        for b in blocks:
            lines = [l for l in b.strip().splitlines() if l.strip() != ""]
            if not lines:
                continue
            # Optional first line index
            if len(lines) >= 2 and ts_re.search(lines[0]) is None:
                lines = lines[1:]  # drop numeric index if present
            if not lines:
                continue
            m = ts_re.search(lines[0])
            if not m:
                # malformed; join as plain text chunk
                entries.append({"start": None, "end": None, "text": "\n".join(lines)})
                continue
            start = ts_to_sec(m.group(1)); end = ts_to_sec(m.group(2))
            text_lines = lines[1:] if len(lines) > 1 else []
            entries.append({"start": start, "end": end, "text": "\n".join(text_lines)})
        return entries

    @staticmethod
    def _parse_vtt(text: str) -> List[Dict]:
        # Remove WEBVTT header if present
        text = re.sub(r"^\s*WEBVTT.*?\n", "", text, flags=re.IGNORECASE|re.DOTALL)
        # Same parsing approach as SRT (with '.' millisecond separator already)
        return CaptionsTranslateService._parse_srt(text)

    @staticmethod
    def _fmt_srt_time(ts: float) -> str:
        ms = int(round(ts*1000))
        h, rem = divmod(ms, 3600000); m, rem = divmod(rem, 60000); s, ms = divmod(rem, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    @staticmethod
    def _fmt_vtt_time(ts: float) -> str:
        ms = int(round(ts*1000))
        h, rem = divmod(ms, 3600000); m, rem = divmod(rem, 60000); s, ms = divmod(rem, 1000)
        return f"{h:02}:{m:02}:{s:02}.{ms:03}"

    @staticmethod
    def _write_srt(path: str, entries: List[Dict]):
        with open(path, "w", encoding="utf-8") as f:
            idx = 1
            for e in entries:
                if e.get("start") is None or e.get("end") is None:
                    # skip malformed in SRT output
                    continue
                f.write(f"{idx}\n")
                f.write(f"{CaptionsTranslateService._fmt_srt_time(e['start'])} --> {CaptionsTranslateService._fmt_srt_time(e['end'])}\n")
                f.write((e.get("text") or "").strip() + "\n\n")
                idx += 1

    @staticmethod
    def _write_vtt(path: str, entries: List[Dict]):
        with open(path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for e in entries:
                if e.get("start") is None or e.get("end") is None:
                    continue
                f.write(f"{CaptionsTranslateService._fmt_vtt_time(e['start'])} --> {CaptionsTranslateService._fmt_vtt_time(e['end'])}\n")
                f.write((e.get("text") or "").strip() + "\n\n")

    # ---------- main ----------
    def process(
        self,
        *,
        target_lang: str,          # e.g., "en", "ja", "es"
        source_lang: Optional[str] = None,  # if None, we’ll still attempt with any->target model
        emit_srt: bool = True,
        emit_vtt: bool = True
    ) -> CaptionsTranslateResult:

        ext = self.captions_path.rsplit(".", 1)[1].lower()

        # Read input into a unified entries list: [{start,end,text}]
        if ext == "srt":
            text = open(self.captions_path, "r", encoding="utf-8", errors="ignore").read()
            entries = self._parse_srt(text)
        elif ext == "vtt":
            text = open(self.captions_path, "r", encoding="utf-8", errors="ignore").read()
            entries = self._parse_vtt(text)
        else:
            data = json.load(open(self.captions_path, "r", encoding="utf-8"))
            if isinstance(data, dict) and "segments" in data:
                entries = [{"start": seg.get("start"), "end": seg.get("end"), "text": seg.get("text","")} for seg in data["segments"]]
            elif isinstance(data, list):
                entries = [{"start": e.get("start"), "end": e.get("end"), "text": e.get("text","")} for e in data]
            else:
                raise ValueError("Unsupported JSON structure. Expect {segments:[{start,end,text}]}, or a list of such objects.")

        # Ensure Argos model and translator
        src = (source_lang or "").strip().lower() or None
        tgt = target_lang.strip().lower()
        self._ensure_model(src or "en", tgt)  # if src unknown, try en->tgt (fallback)
        translator = self._get_translator(src, tgt)

        # Translate text per entry
        out_entries = []
        for e in entries:
            txt = e.get("text") or ""
            try:
                ttxt = translator.translate(txt) if txt else ""
            except Exception:
                # fallback: leave original if translation fails (rare)
                ttxt = txt
            out_entries.append({"start": e.get("start"), "end": e.get("end"), "text": ttxt})

        # Write JSON always
        with open(self.out_json, "w", encoding="utf-8") as f:
            json.dump({"segments": out_entries, "target_lang": tgt, "source_lang": src}, f, ensure_ascii=False, indent=2)

        # Optional SRT / VTT
        srt_path = None
        vtt_path = None
        if emit_srt:
            srt_path = self.out_srt
            self._write_srt(srt_path, out_entries)
        if emit_vtt:
            vtt_path = self.out_vtt
            self._write_vtt(vtt_path, out_entries)

        return CaptionsTranslateResult(
            out_json=self.out_json,
            out_srt=srt_path,
            out_vtt=vtt_path,
            diagnostics={
                "num_segments": len(out_entries),
                "target_lang": tgt,
                "source_lang": src
            }
        )

    def cleanup(self):
        # no temp dirs here, but keep method for symmetry
        pass
