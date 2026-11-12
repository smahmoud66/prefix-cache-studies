"""Build bounded storage variants from the original, digest-locked scientific sources."""
from pathlib import Path
import hashlib
import subprocess
import tempfile
import json
import resource
import time

here = Path(__file__).resolve().parent
first = here.parent / 'exit_cache_20261108/engine.cpp'
second = here.parent / 'exact_tie_20261108/evaluator.cpp'
digests = ['6b3c4b2e042cdca1d433a79349fb22a5e08ab7dbc9fe27bbe5127350a11f4a01',
           '84ed4bc51523c0d855b9514a7ef02596319a95648fe0b7bff962b0247424d549']
for path, digest in zip((first, second), digests):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
before = resource.getrusage(resource.RUSAGE_CHILDREN)
wall = time.monotonic()
with tempfile.TemporaryDirectory() as temp:
    build = Path(temp)
    def patch(s, old, new):
        assert s.count(old) == 1
        return s.replace(old, new)
    evaluator = patch(second.read_text(), '"../exit_cache_20261108/engine.cpp"', '"frozen_engine.hpp"')
    evaluator = patch(evaluator, 'int main() {', 'int frozen_tie_main() {')
    (build / 'frozen_evaluator.hpp').write_text(evaluator)
    for size in (128, 4096):
        (build / 'frozen_engine.hpp').write_text(patch(first.read_text(),
            'constexpr int MAX_CAP = 128;', f'constexpr int MAX_CAP = {size};'))
        subprocess.run(['c++','-std=c++17','-O3','-Wall','-Wextra','-pedantic','-I',temp,
                        str(here/'external_replay.cpp'),'-o',str(here/f'replay_{size}')],check=True)
after = resource.getrusage(resource.RUSAGE_CHILDREN)
print(json.dumps(dict(build_cpu_seconds=after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                      build_wall_seconds=time.monotonic()-wall)))
