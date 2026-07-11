from magnum_monitor.framing import iter_frames


class FakeSerial:
    """Minimal stand-in for a pyserial ``Serial`` object.

    ``stream`` is a list where each element is either a ``bytes`` chunk
    (data that arrived in one burst) or ``None`` (a single read timeout,
    i.e. a quiet gap on the line).
    """

    def __init__(self, stream):
        self.queue = list(stream)
        self.buffer = b""

    @property
    def in_waiting(self):
        return len(self.buffer)

    def read(self, n=1):
        if not self.buffer:
            if not self.queue:
                return b""
            nxt = self.queue.pop(0)
            if nxt is None:
                return b""  # simulated timeout
            self.buffer = nxt
        chunk, self.buffer = self.buffer[:n], self.buffer[n:]
        return chunk


def test_iter_frames_splits_on_gaps():
    fake = FakeSerial([None, None, b"\x01\x02\x03", None, b"\xAA\xBB"])
    gen = iter_frames(fake, settle_time=0)
    assert next(gen) == b"\x01\x02\x03"
    assert next(gen) == b"\xAA\xBB"


def test_iter_frames_ignores_stray_bytes_without_gap():
    # Two bursts with no gap between them: the second is "mid-frame" from
    # the framer's point of view and should be dropped, not mis-framed.
    fake = FakeSerial([None, b"\x01", b"\x02"])
    gen = iter_frames(fake, settle_time=0)
    frame = next(gen)
    assert frame == b"\x01"
