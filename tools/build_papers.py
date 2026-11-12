#!/usr/bin/env python3
"""Package the evaluator's arXiv source and compile its review PDF from that archive."""

import argparse
import gzip
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "papers" / "evaluator" / "main.tex"
NAME = "exact-prefix-cache-continuations-v3.1-arxiv"
STAMP = 1794484800


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{NAME}.tar.gz"

    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as pack:
                member = tarfile.TarInfo(SOURCE.name)
                member.size = SOURCE.stat().st_size
                member.mode = 0o644
                member.mtime = STAMP
                with SOURCE.open("rb") as content:
                    pack.addfile(member, content)

    with tempfile.TemporaryDirectory(prefix="arxiv-build-") as temp:
        work = Path(temp)
        with tarfile.open(archive) as pack:
            member = pack.getmember("main.tex")
            if pack.getnames() != ["main.tex"] or not member.isfile():
                raise ValueError("The source archive must contain only main.tex")
            with pack.extractfile(member) as content:
                (work / member.name).write_bytes(content.read())

        env = os.environ.copy()
        for name in ("TEXINPUTS", "BIBINPUTS", "BSTINPUTS", "TEXMFOUTPUT"):
            env.pop(name, None)
        env.update(TEXMFHOME=str(work / "empty-texmf"), SOURCE_DATE_EPOCH=str(STAMP),
                   FORCE_SOURCE_DATE="1", TZ="UTC")
        command = ["pdflatex", "-no-shell-escape", "-halt-on-error",
                   "-interaction=nonstopmode", "main.tex"]
        for _ in range(2):
            result = subprocess.run(command, cwd=work, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            if result.returncode:
                raise RuntimeError(result.stdout[-3500:])
        log = (work / "main.log").read_text()
        for warning in ("undefined references", "Rerun to get cross-references", "Missing character:"):
            if warning in log:
                raise RuntimeError(warning)
        pdf = output / f"{NAME}.pdf"
        shutil.copyfile(work / "main.pdf", pdf)
    print(f"{archive.name} and {pdf.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    build(parser.parse_args().out.resolve())
