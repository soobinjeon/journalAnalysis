"""Prompt templates for LLM-powered analysis."""

PAPER_SUMMARY_PROMPT = """Analyze the following academic paper and provide a structured summary in Korean.

**Title:** {title}

**Abstract:** {abstract}

Please provide:
1. **핵심 기여 (Key Contribution):** 이 논문이 해결하는 문제와 주요 기여를 1-2문장으로 설명
2. **방법론 (Methodology):** 사용된 접근 방법을 간략히 설명
3. **주요 결과 (Key Results):** 핵심 실험 결과 또는 발견사항
4. **의의 (Significance):** 이 연구가 해당 분야에 미치는 영향

Keep each section concise (1-2 sentences). Write in Korean."""


PAPER_CLASSIFY_PROMPT = """Given the following paper, determine which research areas it belongs to.

**Title:** {title}

**Abstract:** {abstract}

**Available research areas:**
{areas}

Return ONLY the names of matching areas, comma-separated. If no area matches, return "none".
Consider semantic similarity, not just keyword matching."""


TREND_ANALYSIS_PROMPT = """Analyze recent research trends for the area "{area}" based on the following data.

**Recent paper titles:**
{titles}

**Frequently appearing keywords:**
{keywords}

Please provide a trend analysis in Korean:
1. **주요 트렌드 (Main Trends):** 최근 연구의 주요 방향성 (2-3개)
2. **핫 토픽 (Hot Topics):** 특히 주목받는 세부 주제
3. **연구 동향 요약:** 전체적인 연구 흐름에 대한 간략한 분석
4. **향후 전망:** 앞으로 주목할 방향

Keep it concise and insightful. Write in Korean."""


KEYWORD_EXTRACTION_PROMPT = """Extract the most important technical keywords from this paper.

**Title:** {title}

**Abstract:** {abstract}

Return exactly 10 keywords or key phrases, comma-separated.
Focus on technical terms, methods, and domain-specific concepts.
Do NOT include generic academic terms like "study", "analysis", "results"."""
