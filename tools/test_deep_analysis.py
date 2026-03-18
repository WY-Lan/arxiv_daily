"""
Test deep analysis functionality with a real paper.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from tools.paper_analyzer import (
    PaperContentAnalyzer,
    format_deep_analysis_for_xhs,
    format_deep_analysis_for_feishu
)
from tools.llm_client import BailianClient


async def test_deep_analysis(arxiv_id: str = "2401.15884"):
    """
    Test deep analysis with a specific paper.

    Args:
        arxiv_id: arXiv paper ID to test
    """
    # Initialize LLM client
    llm_client = BailianClient()

    # Create analyzer
    analyzer = PaperContentAnalyzer(llm_client=llm_client)

    logger.info(f"Starting deep analysis for paper: {arxiv_id}")

    # Run full analysis
    result = await analyzer.analyze_paper(
        arxiv_id=arxiv_id,
        paper_metadata={
            "title": "Test Paper",
            "arxiv_id": arxiv_id
        }
    )

    if result.error:
        logger.error(f"Analysis failed: {result.error}")
        return

    # Print summary
    print("\n" + "=" * 60)
    print(f"Analysis Complete for {arxiv_id}")
    print("=" * 60)

    # Print sections found
    print(f"\nSections found: {list(result.sections.keys())}")
    for name, section in result.sections.items():
        print(f"  - {name}: {section.word_count} words")

    # Print quality scores
    print(f"\nQuality Scores:")
    print(f"  Overall: {result.overall_quality_score}")
    print(f"  Method: {result.method_analysis.get('score', 'N/A')}")
    print(f"  Experiments: {result.experiment_analysis.get('score', 'N/A')}")
    print(f"  Novelty: {result.novelty_analysis.get('score', 'N/A')}")

    # Print deep analysis
    deep = result.deep_analysis
    if deep and not deep.get("error"):
        print("\n" + "-" * 60)
        print("DEEP ANALYSIS RESULT")
        print("-" * 60)

        # Quick takeaway
        quick = deep.get("quick_takeaway", {})
        if quick:
            print("\n【快速抓要点】")
            print(f"  解决问题: {quick.get('problem_solved', 'N/A')}")
            print(f"  核心方法: {quick.get('core_method', 'N/A')}")
            print(f"  主要结论: {quick.get('main_conclusion', 'N/A')}")

        # Logic flow
        logic = deep.get("logic_flow", {})
        if logic:
            print("\n【逻辑推导】")
            print(f"  背景: {logic.get('background', 'N/A')[:200]}...")
            print(f"  破局: {logic.get('breakthrough', 'N/A')[:200]}...")

        # Technical details
        tech = deep.get("technical_details", {})
        if tech:
            print("\n【技术细节】")
            for key, detail in list(tech.items())[:2]:  # Show first 2
                if isinstance(detail, dict):
                    print(f"  - {detail.get('name', key)}")
                    print(f"    原理: {detail.get('why_works', 'N/A')[:100]}...")

        # Limitations
        limitations = deep.get("limitations", {})
        if limitations:
            print("\n【局限性】")
            for item in limitations.get("method_limitations", [])[:2]:
                print(f"  - 方法局限: {item}")
            for item in limitations.get("potential_issues", [])[:2]:
                print(f"  - 潜在问题: {item}")

        # Concepts
        concepts = deep.get("concept_explanations", [])
        if concepts:
            print("\n【专业概念】")
            for concept in concepts[:3]:
                print(f"  - {concept.get('term', 'N/A')}: {concept.get('definition', 'N/A')[:80]}...")

        # Overall assessment
        assessment = deep.get("overall_assessment", {})
        if assessment:
            print("\n【整体评价】")
            print(f"  创新程度: {assessment.get('innovation_level', 'N/A')}")
            print(f"  实用价值: {assessment.get('practical_value', 'N/A')}")
            print(f"  一句话总结: {assessment.get('take_home_message', 'N/A')}")

        # Test XHS formatting
        print("\n" + "-" * 60)
        print("XHS FORMAT OUTPUT")
        print("-" * 60)
        xhs_output = format_deep_analysis_for_xhs(deep)
        print(xhs_output[:1500] + "..." if len(xhs_output) > 1500 else xhs_output)

        # Test Feishu formatting
        print("\n" + "-" * 60)
        print("FEISHU CARD ELEMENTS")
        print("-" * 60)
        feishu_elements = format_deep_analysis_for_feishu(deep)
        print(f"Generated {len(feishu_elements)} card elements")
        for elem in feishu_elements[:5]:
            print(f"  - {elem}")

        # Save full result to file
        output_file = Path(__file__).parent.parent / "storage" / f"deep_analysis_{arxiv_id.replace('.', '_')}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert to serializable format
        serializable_result = {
            "arxiv_id": result.arxiv_id,
            "overall_quality_score": result.overall_quality_score,
            "method_analysis": result.method_analysis,
            "experiment_analysis": result.experiment_analysis,
            "novelty_analysis": result.novelty_analysis,
            "deep_analysis": result.deep_analysis,
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_result, f, ensure_ascii=False, indent=2)

        print(f"\nFull result saved to: {output_file}")

    else:
        print(f"\nDeep analysis error: {deep.get('error', 'Unknown error')}")


async def main():
    """Run test with command line args."""
    import argparse

    parser = argparse.ArgumentParser(description="Test deep paper analysis")
    parser.add_argument(
        "--arxiv-id",
        default="2401.15884",
        help="arXiv paper ID to analyze (default: 2401.15884)"
    )
    args = parser.parse_args()

    await test_deep_analysis(args.arxiv_id)


if __name__ == "__main__":
    asyncio.run(main())