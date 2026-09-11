from agentsq.monitor.state import Phase


class RunTrace:

    def __init__(self):
        self.phase: Phase | None = None
        self.summary_text: str = ""
        self.curr_sum: str = ""
        self.curr_analysis: str = ""
        self.phase_history: list[Phase] = []
        self.analysis_log: list[str] = []
        self.summary_log: list[str] = []
        self.phase_counter: int = 0
        self.tool_history: list[str] = []

    def to_dict(self):
        return {
            "phase_count": self.phase_counter,
            "final_phase": self.phase.name if self.phase else None,
            "phase_history": [p.name for p in self.phase_history],
            "analysis_log": self.analysis_log,
            "summary_log": self.summary_log,
            "tool_call": self.tool_history,
        }

    def update(self, phase: Phase, summary_text: str, curr_sum: str, curr_analysis: str):
        self.phase = phase
        self.summary_text = summary_text
        self.curr_sum = curr_sum
        self.curr_analysis = curr_analysis
        self.phase_history.append(phase)
        self.analysis_log.append(curr_analysis)
        self.summary_log.append(curr_sum)
        self.phase_counter += 1

    def set_tool_calls(self, tool_hist):
        self.tool_history = tool_hist
