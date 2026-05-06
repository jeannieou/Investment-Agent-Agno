"""Application entrypoint."""

import argparse
import asyncio
import os
import sys

from app.config import get_settings
from app.examples import save_example_artifacts
from app.limits import parse_company_names, usage_note, validate_company_limit
from app.workflows import run_live_workflow, run_mock_workflow


def print_progress(message: str) -> None:
    print(f"[progress] {message}", flush=True)


def configure_event_loop_policy() -> None:
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main() -> None:
    configure_event_loop_policy()
    parser = argparse.ArgumentParser(description="Investment research multi-agent system")
    parser.add_argument(
        "companies",
        nargs="?",
        default="Nvidia,AMD,Intel",
        help="Comma-separated company names. Default: Nvidia,AMD,Intel",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run the Stage 1 deterministic mock workflow.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run the Stage 6 live Agno agent workflow. Requires LLM API credentials.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "deepseek"],
        help="Override LLM_PROVIDER for this run. Used only by --live.",
    )
    parser.add_argument(
        "--save-example",
        action="store_true",
        help="Save memo.md, workflow_state.json, and run_log.json under data/examples/.",
    )
    parser.add_argument(
        "--example-name",
        help="Optional output folder name under data/examples/. Defaults to a company-name slug.",
    )
    args = parser.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    settings = get_settings()
    print("Investment Research Multi-Agent System")
    print(f"LLM provider: {settings.llm_provider}")
    print(usage_note())

    if args.mock and args.live:
        parser.error("Choose only one execution mode: --mock or --live")

    if args.save_example and not args.mock and not args.live:
        args.mock = True

    if not args.mock and not args.live:
        print("Status: use --mock for the stable demo or --live for real Agno agents.")
        return

    try:
        company_names = validate_company_limit(parse_company_names(args.companies))
    except ValueError as exc:
        parser.error(str(exc))
    state = (
        run_live_workflow(company_names, progress_callback=print_progress)
        if args.live
        else run_mock_workflow(company_names)
    )
    print(state.memo)
    print(f"Companies: {len(state.raw_input)}")
    print(f"Agent runs: {len(state.run_log.agent_runs)}")
    print(f"Total latency seconds: {state.run_log.total_latency_seconds}")
    print(f"Cumulative agent latency seconds: {state.run_log.cumulative_agent_latency_seconds}")
    print(f"Identity latency seconds: {state.run_log.identity_latency_seconds}")
    print(f"Parallel pipeline latency seconds: {state.run_log.parallel_pipeline_latency_seconds}")
    print(f"Decision latency seconds: {state.run_log.decision_latency_seconds}")
    if state.run_log.warnings:
        print("Warnings:")
        for warning in state.run_log.warnings:
            print(f"- {warning}")
    if args.save_example:
        output_dir = save_example_artifacts(state, name=args.example_name)
        print(f"Saved example artifacts to: {output_dir}")


if __name__ == "__main__":
    main()
