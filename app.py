"""Interactive chat: ask questions one after another. Type 'exit' (or press Ctrl+C) to quit.

Run:  uv run python app.py
"""

from rich.console import Console

from rag.generate.answer import answer

console = Console()
EXIT_WORDS = {"exit", "quit", "q"}


def main() -> None:
    console.print("[bold]Stride Sports assistant[/] - ask about products or store policies. Type [bold]exit[/] to quit.")
    while True:
        try:
            query = console.input("\n[bold cyan]You:[/] ").strip()
        except (KeyboardInterrupt, EOFError):  # Ctrl+C / Ctrl+D
            break
        if not query:
            continue
        if query.lower() in EXIT_WORDS:
            break

        try:
            with console.status("thinking..."):
                result = answer(query)
        except Exception as e:  # e.g. rate limit or quota: report it and keep the chat running
            console.print("Error:", style="red", end=" ")
            console.print(str(e), markup=False)
            continue

        console.print("[bold green]Assistant:[/]")
        console.print(result.text, markup=False)
        for s in result.sources:
            console.print(f"  [{s.tag}] {s.label}", style="dim", markup=False)
    console.print("\nBye!")


if __name__ == "__main__":
    main()
