from state import status


class renderState():

    def __init__(self):

        self.phase: status|None=  None
        self.summary_text: str = ""
        self.curr_sum:  str = ""
        self.curr_analysis: str = ""
        self.phase_history: list[status] = []
        self.analysis_log: list[str] = []
        self.phase_counter: int = 0
        self.summary_log: list[str] = []
        
    def to_dict(self):

        return {
            "phase_count": self.phase_counter,
            "final_phase": self.phase.name if self.phase else None,
            "phase_history": [s.name for s in self.phase_history],
            "analysis_log": self.analysis_log,
            "final_summary": self.curr_sum,
            "summary_log": self.summary_log,
        }

    def update_state(self, new_phase: status, new_summary_text: str, new_curr_sum: str, new_curr_analysis: str):

        self.phase = new_phase
        self.summary_text = new_summary_text
        self.curr_sum = new_curr_sum
        self.curr_analysis = new_curr_analysis
        self.phase_history.append(new_phase)
        self.analysis_log.append(new_curr_analysis)
        self.summary_log.append(new_curr_sum)
        self.phase_counter += 1

        