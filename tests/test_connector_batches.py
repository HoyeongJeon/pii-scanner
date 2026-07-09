from pii_scanner.connectors.base import Connector, SourceFile
from pii_scanner.config import ScanConfig


class _SF(SourceFile):
    def __init__(self, p): self.logical_path = p
    def __enter__(self): return self.logical_path
    def __exit__(self, *exc): pass


class _Conn(Connector):
    def __init__(self, sfs): self.sfs = sfs
    def iter_files(self, config):
        yield from self.sfs


def test_default_iter_batches_yields_singletons():
    sfs = [_SF("/a"), _SF("/b"), _SF("/c")]
    batches = list(_Conn(sfs).iter_batches(ScanConfig()))
    assert [[sf.logical_path for sf in b] for b in batches] == [["/a"], ["/b"], ["/c"]]
    assert all(len(b) == 1 for b in batches)
