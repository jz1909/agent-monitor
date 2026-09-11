from abc import ABC, abstractmethod

class Segmenter(ABC):
    
    def __init__(self):
            self.blocks: dict[int, str] = {}
            self.prev_idx: int | None = None

    @abstractmethod
    def feed(self, event) -> str | None:
        ...

    @abstractmethod
    def flush(self) -> str | None:
        ...


class SummarySegmenter(Segmenter):

    def feed(self, event) -> str | None:
        idx = event.summary_index
        self.blocks[idx] = self.blocks.get(idx, "") + event.delta

        done = None
        if self.prev_idx is not None and idx != self.prev_idx:
            done = self.blocks.pop(self.prev_idx)

        self.prev_idx = idx
        return done

    def flush(self) -> str | None:
        if self.prev_idx is None:
            return None

        block = self.blocks.pop(self.prev_idx)
        self.blocks.clear()
        self.prev_idx = None
        return block


class LCSSegmenter(Segmenter):

    def __init__(self):
        self.blocks: dict[int, str] = {}
        self.prev_key: tuple[str, int] | None = None

    def feed(self, node, idx, text) -> str|None:
        key = (node, idx)
        self.blocks[key] = self.blocks.get(key, "") + text

        done = None
        if self.prev_key is not None and key != self.prev_key:
            done = self.blocks.pop(self.prev_key)

        self.prev_key = key
        return done
    
    def flush(self) -> str|None:
        if self.prev_key is None:
                return None
    
        block = self.blocks.pop(self.prev_key)
        self.blocks.clear()
        self.prev_key = None
        return block





