class stream_buffer:

    def __init__(self, )->None:
        #(Order, Buffer_text)
        self.buffer: list[tuple[int, str]] = []
        self.counter:int = 0
        self.done: bool = False

    def append(self, append_token:str) -> None:
        self.counter += 1
        self.buffer.append((self.counter, append_token))

    def return_snapshot(self, snapshots_to_return:int) -> list[str]:
        
        last_snapshot:int = self.counter - snapshots_to_return +1
        returned_buffer = []

        for item in self.buffer:
            if item[0] >= last_snapshot:
                returned_buffer.append(item[1])

        return returned_buffer