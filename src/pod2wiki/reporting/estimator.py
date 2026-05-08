"""Cost and workload estimation for pod2wiki scans."""

from __future__ import annotations
from typing import Any, Dict, List
from pod2wiki.models import Config

class CostEstimator:
    """Calculates potential workload and risks for a scan run."""

    def __init__(self, config: Config):
        self.config = config

    def estimate(self, args: Any) -> Dict[str, Any]:
        """
        Produce an estimation report based on run arguments.
        Returns a dict with counts, risks, and messages.
        """
        mode = getattr(args, "mode", "all")
        translate_full = getattr(args, "translate_full", False)
        no_llm = getattr(args, "no_llm", False)
        max_items = getattr(args, "max_items", None)
        
        # 1. Base counts from config
        rss_feeds_count = len([c for c in self.config.channels if c.rss]) + len(self.config.blog_feeds)
        yt_channels_count = len([c for c in self.config.channels if c.youtube])
        
        # 2. Estimated max items per source
        # (Assuming max_items_per_feed and max_videos_per_channel from config or args)
        max_per_rss = getattr(args, "max_items_per_feed", None) or self.config.max_items_per_feed
        max_per_yt = getattr(args, "youtube_max_results", None) or self.config.max_videos_per_channel

        potential_rss = rss_feeds_count * max_per_rss if mode in ("all", "rss") else 0
        potential_yt = yt_channels_count * max_per_yt if mode in ("all", "youtube") else 0
        potential_files = len(getattr(args, "input_file", []))
        
        # 3. Time-window scaling (Heuristic: 1 day gets ~30% of max, 7+ days get 100%)
        days = getattr(args, "days", 7)
        scale_factor = 1.0
        if days < 7:
            scale_factor = 0.3 + (0.7 * (max(0, days - 1) / 6))

        total_potential = int((potential_rss + potential_yt + potential_files) * scale_factor)
        if max_items and total_potential > max_items:
            total_potential = max_items

        # 4. LLM Counts
        summary_calls = total_potential if not no_llm else 0
        translation_calls = total_potential if (not no_llm and translate_full) else 0
        total_llm_calls = summary_calls + translation_calls + (1 if getattr(args, "write_insight_log", False) else 0)

        # 5. Transcription Estimates
        # YouTube always needs text; RSS guess 20%. Scale by time factor.
        estimated_whisper = int((potential_rss * 0.2 + potential_yt) * scale_factor)

        # 5. Risk Assessment
        risks = []
        if yt_channels_count > 5:
            risks.append({
                "level": "high",
                "type": "rate_limit",
                "message": "Multiple YouTube channels detected. High risk of 429 Rate Limit without proxy rotation."
            })
        if total_llm_calls > 30:
            risks.append({
                "level": "medium",
                "type": "cost",
                "message": f"Large batch detected ({total_llm_calls} LLM calls). Verify your API credits."
            })
        if estimated_whisper > 10 and not getattr(args, "no_whisper", False):
            risks.append({
                "level": "medium",
                "type": "performance",
                "message": "Significant local transcription workload expected. Ensure you have a GPU/CPU with sufficient power."
            })

        return {
            "counts": {
                "rss_feeds": rss_feeds_count,
                "youtube_channels": yt_channels_count,
                "max_potential_items": total_potential,
                "llm_summary_calls": summary_calls,
                "llm_translation_calls": translation_calls,
                "total_llm_requests": total_llm_calls,
                "estimated_transcriptions": estimated_whisper,
            },
            "risks": risks,
            "config_summary": {
                "provider": self.config.llm.provider,
                "model": self.config.llm.model,
                "whisper_model": self.config.whisper.model
            }
        }
