class CascadeManager:
    def trigger_cascade(self, project_id: str, trigger_event: str):
        print(f"Cascading updates for {project_id} due to {trigger_event}")
