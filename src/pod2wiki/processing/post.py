"""Post-processing hooks for pod2wiki."""

from __future__ import annotations
from pathlib import Path
from typing import List, Any
from pod2wiki.models import ProcessedItem, Config

class PostProcessor:
    """Base class for post-processing logic."""
    def process(self, items: List[ProcessedItem], config: Config, output_dir: Path):
        pass

class IndexGenerator(PostProcessor):
    """Generates a master index of all summarized items in the run."""
    def process(self, items: List[ProcessedItem], config: Config, output_dir: Path):
        if not items: return
        
        index_path = output_dir / "index.md"
        lines = ["# pod2wiki Scan Index", f"\nGenerated: {items[0].item.date}\n", "| Title | Channel | Source Page |", "| :--- | :--- | :--- |"]
        
        for entry in items:
            sp = Path(entry.source_pages[0]) if entry.source_pages else None
            ref = sp.name if sp else "#"
            lines.append(f"| {entry.item.title} | {entry.item.channel} | [{ref}](sources/{ref}) |")
            
        index_path.write_text("\n".join(lines), encoding="utf-8")

def run_post_processors(items: List[ProcessedItem], config: Config, output_dir: Path):
    """Execute all enabled post-processors, dynamically loaded from config."""
    import importlib
    
    # 1. Default processors
    processors = [IndexGenerator()]
    
    # 2. Dynamic loading from config
    for proc_path in (config.post_processors or []):
        try:
            # Expect format "module.path:ClassName"
            mod_name, class_name = proc_path.split(":")
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, class_name)
            processors.append(cls())
        except Exception as exc:
            import sys
            print(f"[post-processor] Failed to load {proc_path}: {exc}", file=sys.stderr)

    for p in processors:
        try:
            p.process(items, config, output_dir)
        except Exception as exc:
            import sys
            print(f"[post-processor] Error in {p.__class__.__name__}: {exc}", file=sys.stderr)
