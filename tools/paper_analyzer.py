"""
Paper content analyzer for deep PDF analysis.

This module provides tools to download and analyze PDF papers,
extracting key sections for LLM-based quality assessment.
"""
import asyncio
import io
import re
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

import httpx
import pymupdf  # PyMuPDF
from loguru import logger


@dataclass
class PaperSection:
    """Represents a section of a paper."""
    title: str
    content: str
    page_range: Tuple[int, int] = (0, 0)
    word_count: int = 0


@dataclass
class PaperAnalysisResult:
    """Result of paper content analysis."""
    arxiv_id: str
    sections: Dict[str, PaperSection] = field(default_factory=dict)
    method_analysis: Dict[str, Any] = field(default_factory=dict)
    experiment_analysis: Dict[str, Any] = field(default_factory=dict)
    novelty_analysis: Dict[str, Any] = field(default_factory=dict)
    overall_quality_score: float = 0.0
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


class PDFDownloader:
    """Download PDFs from arXiv."""

    @staticmethod
    async def download_pdf(arxiv_id: str, timeout: float = 60.0) -> Optional[bytes]:
        """
        Download PDF from arXiv.

        Args:
            arxiv_id: arXiv paper ID
            timeout: Request timeout in seconds

        Returns:
            PDF content as bytes if successful, None otherwise
        """
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(pdf_url, follow_redirects=True)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.warning(f"Failed to download PDF for {arxiv_id}: {e}")
            return None


class PDFTextExtractor:
    """Extract text and structure from PDF."""

    def __init__(self):
        self.section_patterns = {
            'abstract': r'(?i)^\s*abstract\s*$',
            'introduction': r'(?i)^\s*(1\.\s*)?introduction\s*$',
            'related_work': r'(?i)^\s*(2\.\s*)?related\s+work\s*$',
            'background': r'(?i)^\s*(2\.\s*)?background\s*$',
            'method': r'(?i)^\s*(3\.\s*)?(method|methodology|approach|model|architecture)\s*$',
            'experiments': r'(?i)^\s*(4\.\s*)?(experiment|experimental|evaluation|results?)\s*$',
            'discussion': r'(?i)^\s*discussion\s*$',
            'conclusion': r'(?i)^\s*(5\.\s*)?conclusion\s*$',
            'limitations': r'(?i)^\s*limitation\s*$',
            'references': r'(?i)^\s*reference\s*$',
        }

    def extract_text(self, pdf_bytes: bytes) -> str:
        """
        Extract full text from PDF bytes.

        Args:
            pdf_bytes: PDF content as bytes

        Returns:
            Full text content
        """
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []

            for page in doc:
                text_parts.append(page.get_text())

            doc.close()
            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            return ""

    def extract_sections(self, pdf_bytes: bytes) -> Dict[str, PaperSection]:
        """
        Extract structured sections from PDF.

        Args:
            pdf_bytes: PDF content as bytes

        Returns:
            Dictionary of section name to PaperSection
        """
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            sections = {}
            current_section = None
            section_contents = {}
            section_pages = {}

            for page_num, page in enumerate(doc, 1):
                text = page.get_text()
                lines = text.split('\n')

                for line in lines:
                    line_stripped = line.strip()

                    # Check if this line is a section header
                    for section_name, pattern in self.section_patterns.items():
                        if re.match(pattern, line_stripped):
                            # Save previous section
                            if current_section and current_section in section_contents:
                                sections[current_section] = PaperSection(
                                    title=current_section.capitalize(),
                                    content='\n'.join(section_contents[current_section]),
                                    page_range=section_pages[current_section],
                                    word_count=len(' '.join(section_contents[current_section]).split())
                                )

                            current_section = section_name
                            if current_section not in section_contents:
                                section_contents[current_section] = []
                                section_pages[current_section] = (page_num, page_num)
                            break

                # Add content to current section
                if current_section:
                    section_contents[current_section].append(text)
                    start_page = section_pages[current_section][0]
                    section_pages[current_section] = (start_page, page_num)

            # Save last section
            if current_section and current_section in section_contents:
                sections[current_section] = PaperSection(
                    title=current_section.capitalize(),
                    content='\n'.join(section_contents[current_section]),
                    page_range=section_pages[current_section],
                    word_count=len(' '.join(section_contents[current_section]).split())
                )

            doc.close()
            return sections

        except Exception as e:
            logger.error(f"Failed to extract sections from PDF: {e}")
            return {}

    def get_key_sections_text(self, sections: Dict[str, PaperSection]) -> Dict[str, str]:
        """
        Get text of key sections for analysis.

        Args:
            sections: Extracted sections

        Returns:
            Dictionary of key sections with truncated content
        """
        key_sections = {}

        # Priority order for content analysis
        priority = ['abstract', 'introduction', 'method', 'experiments', 'conclusion']

        for section_name in priority:
            if section_name in sections:
                content = sections[section_name].content
                # Truncate to reasonable length for LLM (first 3000 chars)
                key_sections[section_name] = content[:3000]

        return key_sections


class PaperContentAnalyzer:
    """
    Deep content analyzer using LLM for paper quality assessment.
    """

    def __init__(self, llm_client=None):
        self.pdf_downloader = PDFDownloader()
        self.text_extractor = PDFTextExtractor()
        self.llm_client = llm_client

    async def analyze_paper(self, arxiv_id: str, paper_metadata: Optional[Dict] = None) -> PaperAnalysisResult:
        """
        Perform full content analysis of a paper.

        Args:
            arxiv_id: arXiv paper ID
            paper_metadata: Optional paper metadata (title, abstract, etc.)

        Returns:
            PaperAnalysisResult with detailed analysis
        """
        result = PaperAnalysisResult(arxiv_id=arxiv_id)

        # 1. Download PDF
        pdf_bytes = await self.pdf_downloader.download_pdf(arxiv_id)
        if not pdf_bytes:
            result.error = "Failed to download PDF"
            return result

        # 2. Extract sections
        sections = self.text_extractor.extract_sections(pdf_bytes)
        result.sections = sections

        # 3. Get key sections for analysis
        key_texts = self.text_extractor.get_key_sections_text(sections)

        if not self.llm_client:
            result.error = "LLM client not configured"
            return result

        # 4. Parallel analysis of different aspects
        try:
            method_task = self._analyze_method(
                key_texts.get('method', ''),
                key_texts.get('introduction', '')
            )
            experiment_task = self._analyze_experiments(key_texts.get('experiments', ''))
            novelty_task = self._analyze_novelty(
                key_texts.get('introduction', ''),
                key_texts.get('abstract', ''),
                key_texts.get('related_work', '')
            )

            result.method_analysis = await method_task
            result.experiment_analysis = await experiment_task
            result.novelty_analysis = await novelty_task

            # 5. Calculate overall quality score
            result.overall_quality_score = self._calculate_overall_score(result)

        except Exception as e:
            logger.error(f"Error analyzing paper {arxiv_id}: {e}")
            result.error = str(e)

        return result

    async def _analyze_method(self, method_text: str, intro_text: str) -> Dict[str, Any]:
        """
        Analyze the methodology section for innovation and rigor.
        """
        if not method_text:
            return {"score": 0.5, "analysis": "Method section not found", "concerns": []}

        prompt = """You are an expert AI researcher evaluating a paper's methodology.

Please analyze the following method section and introduction to evaluate:

1. **Core Innovation** (0-1): What is the key novel technical contribution?
2. **Technical Rigor** (0-1): Is the method well-defined and theoretically sound?
3. **Feasibility** (0-1): Can this method actually be implemented?
4. **Comparison to Baselines** (0-1): Does it clearly differ from existing approaches?

Introduction (context):
{intro_text[:1500]}

Method Section:
{method_text[:2500]}

Return JSON format:
{{
  "score": 0.75,
  "core_innovation": "Description of main technical contribution",
  "technical_rigor_score": 0.8,
  "feasibility_score": 0.7,
  "comparison_score": 0.75,
  "strengths": ["Strength 1", "Strength 2"],
  "concerns": ["Concern 1", "Concern 2"],
  "is_incremental": false,
  "has_theoretical_guarantee": true
}}
""".format(intro_text=intro_text, method_text=method_text)

        try:
            messages = [
                {"role": "system", "content": "You are an expert paper reviewer focusing on methodology assessment."},
                {"role": "user", "content": prompt}
            ]

            result = await self.llm_client.generate_json(
                messages=messages,
                temperature=0.3,
                max_tokens=1500
            )

            return {
                "score": float(result.get("score", 0.5)),
                "core_innovation": result.get("core_innovation", ""),
                "technical_rigor_score": float(result.get("technical_rigor_score", 0.5)),
                "feasibility_score": float(result.get("feasibility_score", 0.5)),
                "comparison_score": float(result.get("comparison_score", 0.5)),
                "strengths": result.get("strengths", []),
                "concerns": result.get("concerns", []),
                "is_incremental": result.get("is_incremental", False),
                "has_theoretical_guarantee": result.get("has_theoretical_guarantee", False),
            }
        except Exception as e:
            logger.warning(f"Method analysis failed: {e}")
            return {"score": 0.5, "analysis": f"Analysis failed: {e}", "concerns": []}

    async def _analyze_experiments(self, exp_text: str) -> Dict[str, Any]:
        """
        Analyze the experiments section for rigor and completeness.
        """
        if not exp_text:
            return {"score": 0.5, "analysis": "Experiments section not found", "concerns": ["No experiments"]}

        prompt = """You are an expert reviewer evaluating a paper's experimental validation.

Please analyze the following experiments section:

{exp_text[:3000]}

Evaluate on these dimensions (0-1 scale):
1. **Dataset Diversity**: Are datasets diverse and representative?
2. **Baseline Quality**: Are baseline methods appropriate and strong?
3. **Metric Completeness**: Are evaluation metrics comprehensive?
4. **Ablation Studies**: Are there ablation studies validating key components?
5. **Statistical Significance**: Are results statistically significant?
6. **Reproducibility**: Are implementation details sufficient for reproduction?

Return JSON format:
{{
  "score": 0.75,
  "dataset_diversity": 0.8,
  "baseline_quality": 0.7,
  "metric_completeness": 0.75,
  "ablation_quality": 0.6,
  "statistical_rigor": 0.7,
  "reproducibility_score": 0.65,
  "strengths": ["Strength 1"],
  "weaknesses": ["Weakness 1"],
  "red_flags": ["Red flag if any"]
}}
""".format(exp_text=exp_text)

        try:
            messages = [
                {"role": "system", "content": "You are an expert in experimental validation and reproducibility."},
                {"role": "user", "content": prompt}
            ]

            result = await self.llm_client.generate_json(
                messages=messages,
                temperature=0.3,
                max_tokens=1500
            )

            return {
                "score": float(result.get("score", 0.5)),
                "dataset_diversity": float(result.get("dataset_diversity", 0.5)),
                "baseline_quality": float(result.get("baseline_quality", 0.5)),
                "metric_completeness": float(result.get("metric_completeness", 0.5)),
                "ablation_quality": float(result.get("ablation_quality", 0.5)),
                "statistical_rigor": float(result.get("statistical_rigor", 0.5)),
                "reproducibility_score": float(result.get("reproducibility_score", 0.5)),
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "red_flags": result.get("red_flags", []),
            }
        except Exception as e:
            logger.warning(f"Experiment analysis failed: {e}")
            return {"score": 0.5, "analysis": f"Analysis failed: {e}", "concerns": []}

    async def _analyze_novelty(self, intro_text: str, abstract_text: str, related_work_text: str) -> Dict[str, Any]:
        """
        Analyze the novelty and contribution of the paper.
        """
        prompt = """You are an expert in assessing research novelty and contributions.

Based on the following sections, evaluate the paper's true novelty:

Abstract:
{abstract_text[:1000]}

Introduction:
{intro_text[:1500]}

Related Work (if available):
{related_work_text[:1000]}

Evaluate:
1. **Problem Novelty** (0-1): Is the problem itself new or important?
2. **Solution Novelty** (0-1): Is the approach genuinely new?
3. **Contribution Clarity** (0-1): Are contributions clearly stated?
4. **Gap Identification** (0-1): Does it clearly identify what was missing before?

Return JSON format:
{{
  "score": 0.75,
  "problem_novelty": 0.8,
  "solution_novelty": 0.7,
  "contribution_clarity": 0.75,
  "gap_identification": 0.8,
  "key_contributions": ["Contribution 1", "Contribution 2"],
  "claimed_novelty": "What the authors claim is new",
  "assessment": "Your assessment of true novelty",
  "similar_to": ["Related paper/concept if it seems similar"],
  "concern_flags": ["Red flag if any"]
}}
""".format(
            abstract_text=abstract_text,
            intro_text=intro_text,
            related_work_text=related_work_text or "Not available"
        )

        try:
            messages = [
                {"role": "system", "content": "You are an expert in research novelty assessment. Be critical and fair."},
                {"role": "user", "content": prompt}
            ]

            result = await self.llm_client.generate_json(
                messages=messages,
                temperature=0.3,
                max_tokens=1500
            )

            return {
                "score": float(result.get("score", 0.5)),
                "problem_novelty": float(result.get("problem_novelty", 0.5)),
                "solution_novelty": float(result.get("solution_novelty", 0.5)),
                "contribution_clarity": float(result.get("contribution_clarity", 0.5)),
                "gap_identification": float(result.get("gap_identification", 0.5)),
                "key_contributions": result.get("key_contributions", []),
                "claimed_novelty": result.get("claimed_novelty", ""),
                "assessment": result.get("assessment", ""),
                "similar_to": result.get("similar_to", []),
                "concern_flags": result.get("concern_flags", []),
            }
        except Exception as e:
            logger.warning(f"Novelty analysis failed: {e}")
            return {"score": 0.5, "analysis": f"Analysis failed: {e}", "concerns": []}

    def _calculate_overall_score(self, result: PaperAnalysisResult) -> float:
        """
        Calculate overall quality score from component analyses.
        """
        method_score = result.method_analysis.get("score", 0.5)
        exp_score = result.experiment_analysis.get("score", 0.5)
        novelty_score = result.novelty_analysis.get("score", 0.5)

        # Weighted combination: novelty and method matter most
        weights = {
            "novelty": 0.40,
            "method": 0.35,
            "experiments": 0.25
        }

        overall = (
            weights["novelty"] * novelty_score +
            weights["method"] * method_score +
            weights["experiments"] * exp_score
        )

        return round(overall, 2)


class PaperComparisonAnalyzer:
    """
    Compare papers to identify novelty and differentiation.
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def compare_with_existing(
        self,
        target_paper: Dict[str, Any],
        existing_papers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare target paper with existing papers to assess true novelty.

        Args:
            target_paper: Target paper with title, abstract, sections
            existing_papers: List of existing papers in the database

        Returns:
            Comparison analysis result
        """
        if not self.llm_client:
            return {"comparison_score": 0.5, "error": "LLM client not configured"}

        # Format related papers
        related_formatted = self._format_related_papers(existing_papers)

        prompt = """You are an expert in comparing research papers to assess true novelty and differentiation.

Target Paper:
Title: {title}
Abstract: {abstract}
Key Contributions (from analysis): {contributions}

Existing Papers in the Same Area:
{related_papers}

Please analyze:
1. How is the target paper different from existing work?
2. Does it solve a problem that existing papers don't?
3. Is the method a significant departure or just a variation?
4. Are there any papers that already did something very similar?

Return JSON format:
{{
  "differentiation_score": 0.75,
  "novelty_vs_existing": "Description of how it's different",
  "similar_papers": ["Paper ID/name if similar"],
  "gaps_addressed": ["Gap 1", "Gap 2"],
  "is_significant_advance": true,
  "redundancy_concerns": ["Concern if any"],
  "recommendation": "Whether this adds substantial new knowledge"
}}
""".format(
            title=target_paper.get("title", ""),
            abstract=target_paper.get("abstract", "")[:800],
            contributions=target_paper.get("key_contributions", []),
            related_papers=related_formatted
        )

        try:
            messages = [
                {"role": "system", "content": "You are an expert research analyst specializing in novelty assessment."},
                {"role": "user", "content": prompt}
            ]

            result = await self.llm_client.generate_json(
                messages=messages,
                temperature=0.3,
                max_tokens=1500
            )

            return {
                "comparison_score": float(result.get("differentiation_score", 0.5)),
                "novelty_vs_existing": result.get("novelty_vs_existing", ""),
                "similar_papers": result.get("similar_papers", []),
                "gaps_addressed": result.get("gaps_addressed", []),
                "is_significant_advance": result.get("is_significant_advance", False),
                "redundancy_concerns": result.get("redundancy_concerns", []),
                "recommendation": result.get("recommendation", ""),
            }
        except Exception as e:
            logger.warning(f"Paper comparison failed: {e}")
            return {"comparison_score": 0.5, "error": str(e)}

    def _format_related_papers(self, papers: List[Dict[str, Any]]) -> str:
        """Format related papers for comparison prompt."""
        formatted = []
        for i, paper in enumerate(papers[:5], 1):  # Limit to 5 papers
            formatted.append(
                f"{i}. {paper.get('title', 'Unknown')}\n"
                f"   Abstract: {paper.get('abstract', '')[:200]}..."
            )
        return "\n\n".join(formatted) if formatted else "No existing papers found."
