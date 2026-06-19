from dataclasses import dataclass


@dataclass
class TaskItem:
    task_type: str
    value: str
