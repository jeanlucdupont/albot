import argparse
import asyncio
import os

from .storage import ROOT


async def run(args):
    from .runner import comparison, control, investigate
    if args.command == "control":
        rows = [await control(mode) for mode in ("permissive", "guarded")]
    elif args.command == "compare":
        # New process, fresh conversation, unique empty artifact namespace for each arm.
        rows = [await investigate("poisoned", mode) for mode in ("permissive", "guarded")]
    else:
        rows = [await investigate(args.scenario, args.mode)]
    comparison(rows)
    return 0 if all(r["status"] == "complete" for r in rows) else 1


def main():
    parser = argparse.ArgumentParser(description="MCP SOC Guard - all exports are LOCAL SIMULATIONS")
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("investigate")
    inv.add_argument("--scenario", choices=["clean", "poisoned"], default="clean")
    inv.add_argument("--mode", choices=["guarded", "permissive"], default="guarded")
    sub.add_parser("control", help="Deterministic real MCP checks; NO LLM or API key")
    sub.add_parser("compare", help="One poisoned run per mode, with independent sessions")
    demo = sub.add_parser("demo", help="Local browser replay of recorded artifacts; no model calls")
    demo.add_argument("--port", type=int, choices=range(0, 65536), metavar="PORT", default=8765)
    demo.add_argument("--open-browser", action="store_true")
    demo.add_argument("--list-runs", action="store_true")
    for slot in ("clean", "permissive", "guarded", "control-permissive", "control-guarded"):
        demo.add_argument("--" + slot + "-run", metavar="RUN_ID")
    args = parser.parse_args()
    if args.command == "demo":
        from .demo import launch
        launch(args)
        return
    from dotenv import load_dotenv
    from .runner import console
    load_dotenv(ROOT.parent / ".env", override=False)
    if args.command != "control" and not all(os.getenv(k) for k in ("OPENAI_API_KEY", "OPENAI_MODEL")):
        console.print("Live model demonstration UNVERIFIED: set OPENAI_API_KEY and OPENAI_MODEL. Run 'python -m soc_guard control' without credentials.", style="yellow")
        raise SystemExit(2)
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        console.print("Interrupted; any partial audit/export artifacts remain in simulation/.")
        raise SystemExit(130)
