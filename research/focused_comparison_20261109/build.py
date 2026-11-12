"""Import the archived evaluator into one C++ translation unit without altering its source."""
from pathlib import Path
import hashlib
import json
import resource
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parent
previous = root.parent / 'exact_tie_20261108'
core = root.parent / 'exit_cache_20261108/engine.cpp'
source = previous / 'evaluator.cpp'
assert hashlib.sha256(core.read_bytes()).hexdigest() == '6b3c4b2e042cdca1d433a79349fb22a5e08ab7dbc9fe27bbe5127350a11f4a01'
assert hashlib.sha256(source.read_bytes()).hexdigest() == '84ed4bc51523c0d855b9514a7ef02596319a95648fe0b7bff962b0247424d549'
start = time.monotonic()
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp)
    text = source.read_text()
    assert text.count('#include "../exit_cache_20261108/engine.cpp"') == 1
    assert text.count('int main() {') == 1
    text = text.replace('#include "../exit_cache_20261108/engine.cpp"', '#include "frozen_engine.hpp"')
    text = text.replace('int main() {', 'int archived_evaluator_main() {')
    (path / 'frozen_evaluator.hpp').write_text(text)
    (path / 'frozen_engine.hpp').write_bytes(core.read_bytes())
    subprocess.run(['c++', '-std=c++17', '-O3', '-Wall', '-Wextra', '-pedantic', '-I', tmp,
                    str(root / 'evaluator.cpp'), '-o', str(root / 'evaluator')], check=True)
usage = resource.getrusage(resource.RUSAGE_CHILDREN)
print(json.dumps(dict(cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-start)))
