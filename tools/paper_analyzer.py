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

from config.prompts import load_prompt


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
    deep_analysis: Dict[str, Any] = field(default_factory=dict)  # New: structured deep analysis
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
        # More flexible section patterns - match section headers with optional numbering
        # and allow content to follow on the same line
        self.section_patterns = {
            'abstract': r'(?i)^(?:\d+\.?\s*)?abstract\s*',
            'introduction': r'(?i)^(?:\d+\.?\s*)?introduction\s*$',
            'related_work': r'(?i)^(?:\d+\.?\s*)?related\s*[-–]?\s*work\s*$',
            'background': r'(?i)^(?:\d+\.?\s*)?background\s*$',
            'method': r'(?i)^(?:\d+\.?\s*)?(method|methodology|approach|model|architecture|proposed\s+method|our\s+approach)\s*$',
            'experiments': r'(?i)^(?:\d+\.?\s*)?(experiment|experimental|evaluation|results?|experiments)\s*$',
            'discussion': r'(?i)^(?:\d+\.?\s*)?discussion\s*$',
            'conclusion': r'(?i)^(?:\d+\.?\s*)?(conclusion|conclusions)\s*$',
            'limitations': r'(?i)^(?:\d+\.?\s*)?limitations?\s*$',
            'references': r'(?i)^(?:\d+\.?\s*)?references?\s*$',
        }
        # Order of sections for priority
        self.section_priority = [
            'abstract', 'introduction', 'related_work', 'background',
            'method', 'experiments', 'discussion', 'limitations', 'conclusion'
        ]

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
            section_lines = {}  # Store lines per section
            section_pages = {}

            for page_num, page in enumerate(doc, 1):
                text = page.get_text()
                lines = text.split('\n')

                for line in lines:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue

                    # Check if this line is a section header
                    matched_section = None
                    remaining_content = None

                    for section_name, pattern in self.section_patterns.items():
                        match = re.match(pattern, line_stripped)
                        if match:
                            matched_section = section_name
                            # Get content after the header on the same line
                            remaining_content = line_stripped[match.end():].strip()
                            break

                    if matched_section:
                        # Save previous section before switching
                        if current_section and current_section in section_lines:
                            content = '\n'.join(section_lines[current_section])
                            sections[current_section] = PaperSection(
                                title=current_section.capitalize(),
                                content=content,
                                page_range=section_pages[current_section],
                                word_count=len(content.split())
                            )

                        # Start new section
                        current_section = matched_section
                        if current_section not in section_lines:
                            section_lines[current_section] = []
                            section_pages[current_section] = (page_num, page_num)

                        # Add content that follows the header on the same line
                        if remaining_content:
                            section_lines[current_section].append(remaining_content)
                    elif current_section:
                        # Add line to current section
                        section_lines[current_section].append(line_stripped)
                        start_page = section_pages[current_section][0]
                        section_pages[current_section] = (start_page, page_num)

            # Save last section
            if current_section and current_section in section_lines:
                content = '\n'.join(section_lines[current_section])
                sections[current_section] = PaperSection(
                    title=current_section.capitalize(),
                    content=content,
                    page_range=section_pages[current_section],
                    word_count=len(content.split())
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
            logger.debug("Creating analysis tasks...")
            method_task = self._analyze_method(
                key_texts.get('method', ''),
                key_texts.get('introduction', '')
            )
            logger.debug("Created method_task")
            experiment_task = self._analyze_experiments(key_texts.get('experiments', ''))
            logger.debug("Created experiment_task")
            novelty_task = self._analyze_novelty(
                key_texts.get('introduction', ''),
                key_texts.get('abstract', ''),
                key_texts.get('related_work', '')
            )
            logger.debug("Created novelty_task")
            deep_task = self._analyze_deep(sections, paper_metadata)
            logger.debug("Created deep_task")

            logger.debug("Awaiting method_task...")
            result.method_analysis = await method_task
            logger.debug(f"method_analysis result: {result.method_analysis}")

            logger.debug("Awaiting experiment_task...")
            result.experiment_analysis = await experiment_task
            logger.debug(f"experiment_analysis result: {result.experiment_analysis}")

            logger.debug("Awaiting novelty_task...")
            result.novelty_analysis = await novelty_task
            logger.debug(f"novelty_analysis result: {result.novelty_analysis}")

            logger.debug("Awaiting deep_task...")
            result.deep_analysis = await deep_task
            logger.debug(f"deep_analysis result: {result.deep_analysis}")

            # 5. Calculate overall quality score
            result.overall_quality_score = self._calculate_overall_score(result)

        except Exception as e:
            import traceback
            logger.error(f"Error analyzing paper {arxiv_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
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
{intro_text}

Method Section:
{method_text}

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
""".format(intro_text=intro_text[:1500], method_text=method_text[:2500])

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

            # Debug: Log the actual result type
            logger.debug(f"Method analysis result type: {type(result)}")

            # Check for error in result
            if isinstance(result, dict) and result.get("error"):
                logger.warning(f"LLM returned error: {result.get('error')}")
                return {"score": 0.5, "analysis": f"LLM error: {result.get('error')}", "concerns": []}

            if not isinstance(result, dict):
                logger.warning(f"Unexpected result type: {type(result)}")
                return {"score": 0.5, "analysis": f"Unexpected result type: {type(result)}", "concerns": []}

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

{exp_text}

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
""".format(exp_text=exp_text[:3000])

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

            # Debug: Log the actual result type
            logger.debug(f"Experiment analysis result type: {type(result)}")

            # Check for error in result
            if isinstance(result, dict) and result.get("error"):
                logger.warning(f"LLM returned error: {result.get('error')}")
                return {"score": 0.5, "analysis": f"LLM error: {result.get('error')}", "concerns": []}

            if not isinstance(result, dict):
                logger.warning(f"Unexpected result type: {type(result)}")
                return {"score": 0.5, "analysis": f"Unexpected result type: {type(result)}", "concerns": []}

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
{abstract_text}

Introduction:
{intro_text}

Related Work (if available):
{related_work_text}

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
            abstract_text=abstract_text[:1000],
            intro_text=intro_text[:1500],
            related_work_text=(related_work_text or "Not available")[:1000]
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

            # Debug: Log the actual result type
            logger.debug(f"Novelty analysis result type: {type(result)}")

            # Check for error in result
            if isinstance(result, dict) and result.get("error"):
                logger.warning(f"LLM returned error: {result.get('error')}")
                return {"score": 0.5, "analysis": f"LLM error: {result.get('error')}", "concerns": []}

            if not isinstance(result, dict):
                logger.warning(f"Unexpected result type: {type(result)}")
                return {"score": 0.5, "analysis": f"Unexpected result type: {type(result)}", "concerns": []}

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

    async def _analyze_deep(self, sections: Dict[str, PaperSection], paper_metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Perform deep structured analysis for reader-friendly interpretation.

        This method generates the 5-component deep analysis:
        1. Quick takeaway (problem, method, conclusion)
        2. Logic flow (background → breakthrough → breakdown)
        3. Technical details (key implementation tricks)
        4. Limitations analysis
        5. Concept explanations

        Args:
            sections: Extracted paper sections
            paper_metadata: Optional metadata (title, authors, etc.)

        Returns:
            Structured deep analysis result
        """
        if not self.llm_client:
            return {"error": "LLM client not configured"}

        # Load the deep analysis prompt
        try:
            system_prompt = load_prompt("deep_analysis")
        except FileNotFoundError:
            logger.error("deep_analysis.txt prompt not found")
            return {"error": "Deep analysis prompt template not found"}

        # Prepare full paper content for analysis
        paper_content = self._prepare_full_content(sections, paper_metadata)

        # Build messages for LLM
        messages = [
            {"role": "user", "content": f"{system_prompt}\n\n## 论文全文内容\n\n{paper_content}"}
        ]

        try:
            result = await self.llm_client.generate_json(
                messages=messages,
                temperature=0.3,
                max_tokens=4000  # Need more tokens for detailed analysis
            )

            # Debug: Log the actual result type
            logger.debug(f"Deep analysis result type: {type(result)}")

            # Check for error in result
            if isinstance(result, dict) and result.get("error"):
                logger.warning(f"LLM returned error: {result.get('error')}")
                return {"error": f"LLM error: {result.get('error')}"}

            if not isinstance(result, dict):
                logger.warning(f"Unexpected result type: {type(result)}")
                return {"error": f"Unexpected result type: {type(result)}"}

            # Validate and structure the result
            return {
                "quick_takeaway": result.get("quick_takeaway", {}),
                "logic_flow": result.get("logic_flow", {}),
                "technical_details": result.get("technical_details", {}),
                "limitations": result.get("limitations", {}),
                "concept_explanations": result.get("concept_explanations", []),
                "reproducibility": result.get("reproducibility", {}),
                "overall_assessment": result.get("overall_assessment", {}),
            }
        except Exception as e:
            logger.error(f"Deep analysis failed: {e}")
            return {"error": str(e)}

    def _prepare_full_content(self, sections: Dict[str, PaperSection], paper_metadata: Optional[Dict] = None) -> str:
        """
        Prepare full paper content for deep analysis.

        Combines all key sections with appropriate truncation to stay within
        LLM context limits while preserving essential content.

        Args:
            sections: Extracted paper sections
            paper_metadata: Optional paper metadata

        Returns:
            Formatted paper content string
        """
        content_parts = []

        # Add metadata if available
        if paper_metadata:
            if paper_metadata.get("title"):
                content_parts.append(f"# 标题: {paper_metadata['title']}\n")
            if paper_metadata.get("authors"):
                authors = paper_metadata["authors"]
                if isinstance(authors, list):
                    authors = ", ".join(authors[:5])  # Limit to first 5 authors
                content_parts.append(f"作者: {authors}\n")

        # Add each section with appropriate length limits
        section_limits = {
            "abstract": 1500,
            "introduction": 3000,
            "method": 5000,
            "experiments": 4000,
            "conclusion": 2000,
            "related_work": 2000,
            "discussion": 2000,
            "limitations": 1500,
        }

        for section_name in ["abstract", "introduction", "related_work", "method", "experiments", "discussion", "limitations", "conclusion"]:
            if section_name in sections:
                section = sections[section_name]
                limit = section_limits.get(section_name, 2000)
                content = section.content[:limit]

                # Format section header
                section_title = section_name.replace("_", " ").title()
                content_parts.append(f"\n## {section_title}\n\n{content}\n")

        return "\n".join(content_parts)

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


def format_deep_analysis_for_xhs(
    deep_analysis: Dict[str, Any],
    paper_metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format deep analysis result for Xiaohongshu publishing.
    XHS has a 1000 character limit, so this is a condensed version.

    Args:
        deep_analysis: Deep analysis result from PaperContentAnalyzer
        paper_metadata: Optional paper metadata (title, authors, arxiv_id, etc.)

    Returns:
        Formatted markdown string for XHS (under 1000 chars)
    """
    if not deep_analysis or deep_analysis.get("error"):
        return ""

    parts = []

    # 0. 论文基本信息（作者、单位等）
    if paper_metadata:
        parts.append("📄【论文信息】\n")
        # 标题（可选，如果有需要可以加）
        # 作者信息
        authors = paper_metadata.get("authors", [])
        if authors:
            if isinstance(authors, list):
                # 最多显示3位作者
                author_str = ", ".join(authors[:3])
                if len(authors) > 3:
                    author_str += " 等"
            else:
                author_str = str(authors)[:50]
            parts.append(f"👤 作者: {author_str}\n")
        # arxiv ID
        arxiv_id = paper_metadata.get("arxiv_id", "")
        if arxiv_id:
            parts.append(f"🔗 arXiv: {arxiv_id}\n")

    # 1. 快速抓要点（精简）
    quick = deep_analysis.get("quick_takeaway", {})
    if quick:
        parts.append("🎯【快速抓要点】\n")
        if quick.get("problem_solved"):
            # 截断过长的文本
            text = quick['problem_solved'][:60] + "..." if len(quick['problem_solved']) > 60 else quick['problem_solved']
            parts.append(f"❓ {text}\n")
        if quick.get("core_method"):
            text = quick['core_method'][:60] + "..." if len(quick['core_method']) > 60 else quick['core_method']
            parts.append(f"💡 {text}\n")
        if quick.get("main_conclusion"):
            text = quick['main_conclusion'][:60] + "..." if len(quick['main_conclusion']) > 60 else quick['main_conclusion']
            parts.append(f"✅ {text}\n")

    # 2. 逻辑推导（精简，只保留背景和破局）
    logic = deep_analysis.get("logic_flow", {})
    if logic:
        parts.append("\n🔍【逻辑推导】\n")
        if logic.get("breakthrough"):
            text = logic['breakthrough'][:100] + "..." if len(logic['breakthrough']) > 100 else logic['breakthrough']
            parts.append(f"破局: {text}\n")

    # 3. 技术细节（只保留1个核心技巧）
    tech = deep_analysis.get("technical_details", {})
    if tech:
        parts.append("\n⚙️【技术细节】\n")
        # 只取第一个技巧
        for key, detail in list(tech.items())[:1]:
            if isinstance(detail, dict) and detail.get("name"):
                parts.append(f"▸ {detail.get('name', '核心技巧')}\n")
                if detail.get("why_works"):
                    text = detail['why_works'][:80] + "..." if len(detail['why_works']) > 80 else detail['why_works']
                    parts.append(f"  原理: {text}\n")

    # 4. 局限性（只保留方法局限，最多2条）
    limitations = deep_analysis.get("limitations", {})
    if limitations:
        parts.append("\n⚠️【局限性】\n")
        method_lims = limitations.get("method_limitations", [])[:2]
        for item in method_lims:
            text = item[:50] + "..." if len(item) > 50 else item
            parts.append(f"• {text}\n")

    # 5. 专业概念（最多2个，简化格式）
    concepts = deep_analysis.get("concept_explanations", [])
    if concepts:
        parts.append("\n📚【核心概念】\n")
        for concept in concepts[:2]:
            if concept.get("term"):
                def_text = concept.get('definition', '')[:40] + "..." if len(concept.get('definition', '')) > 40 else concept.get('definition', '')
                parts.append(f"• {concept['term']}: {def_text}\n")

    # 6. 复现指南（简化为一行）
    reproducibility = deep_analysis.get("reproducibility", {})
    if reproducibility:
        parts.append("\n🔨【复现指南】\n")
        code = reproducibility.get("has_code", "无")
        diff = reproducibility.get("reproduce_difficulty", "未知")
        parts.append(f"代码: {code} | 难度: {diff}\n")

    # 7. 整体评价（精简）
    assessment = deep_analysis.get("overall_assessment", {})
    if assessment:
        parts.append("\n📊【整体评价】\n")
        innovation = assessment.get("innovation_level", "未知")
        practical = assessment.get("practical_value", "未知")
        parts.append(f"创新: {innovation} | 实用: {practical}\n")
        if assessment.get("take_home_message"):
            text = assessment['take_home_message'][:80] + "..." if len(assessment['take_home_message']) > 80 else assessment['take_home_message']
            parts.append(f"\n💬 {text}\n")

    result = "".join(parts)

    # 最终检查：如果仍超过900字符，进一步压缩
    if len(result) > 900:
        # 移除概念解释部分
        if "📚【核心概念】" in result:
            lines = result.split("\n")
            result_lines = []
            skip = False
            for line in lines:
                if "📚【核心概念】" in line:
                    skip = True
                elif skip and line.startswith("\n"):
                    skip = False
                    result_lines.append(line)
                elif not skip:
                    result_lines.append(line)
            result = "\n".join(result_lines)

    return result
