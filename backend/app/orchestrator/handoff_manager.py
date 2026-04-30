class HandoffManager:
    def prepare_handoff(self, project_id: str, source_stage: str, target_stage: str):
        print(f"Preparing handoff from {source_stage} to {target_stage}")
