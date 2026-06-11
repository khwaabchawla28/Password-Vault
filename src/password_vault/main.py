"""
main.py

CLI entry point — wires user input to vault operations.

Commands:
  init             Create a new empty vault
  add <name>       Add a credential entry
  get <name>       Show an entry's details (with --copy for clipboard)
  search <query>   Fuzzy search entries by name
  list             List all entry names
  delete <name>    Remove an entry
  change-password  Rotate the master password
  gen [length]     Generate a random password (no vault needed)
  qr               Export vault as QR code for mobile transfer
  serve            Start local API server for browser extension

Master password is NEVER accepted as a CLI flag — it would leak into
shell history and process listings. All prompts use getpass.getpass()
(the same primitive sudo uses) so the password is never echoed.
"""

import getpass
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from password_vault.constants import (
    DEFAULT_GENERATED_PASSWORD_LENGTH,
    DEFAULT_VAULT_PATH,
    MINIMUM_MASTER_PASSWORD_LENGTH,
    MSG_ENTRY_ADDED,
    MSG_ENTRY_ALREADY_EXISTS,
    MSG_ENTRY_DELETED,
    MSG_ENTRY_NOT_FOUND,
    MSG_MASTER_PASSWORD_CHANGED,
    MSG_MASTER_PASSWORD_EMPTY,
    MSG_MASTER_PASSWORD_TOO_SHORT,
    MSG_PASSWORDS_DO_NOT_MATCH,
    MSG_VAULT_ALREADY_EXISTS,
    MSG_VAULT_CREATED,
    MSG_VAULT_EMPTY,
    MSG_VAULT_NOT_FOUND,
    MSG_WRONG_MASTER_PASSWORD,
    PROMPT_ENTRY_NOTES,
    PROMPT_ENTRY_PASSWORD,
    PROMPT_ENTRY_URL,
    PROMPT_ENTRY_USERNAME,
    PROMPT_MASTER_PASSWORD,
    PROMPT_MASTER_PASSWORD_CONFIRM,
    PROMPT_MASTER_PASSWORD_NEW,
)
from password_vault.crypto import WrongPasswordError
from password_vault.generator import PasswordTooShortError, generate_password
from password_vault.search import fuzzy_search
from password_vault.vault import (
    Entry,
    EntryAlreadyExistsError,
    EntryNotFoundError,
    UnlockedVault,
    VaultAlreadyExistsError,
    VaultError,
    VaultFormatError,
    VaultNotFoundError,
)

app = typer.Typer(
    name="pvt",
    help="Encrypted password vault — one master password protects everything.",
    add_completion=False,
)
console = Console(stderr=True)
printer = Console()


def _vault_path(vault: Optional[Path]) -> Path:
    return vault if vault else DEFAULT_VAULT_PATH


def _prompt_master(message: str = PROMPT_MASTER_PASSWORD) -> str:
    pw = getpass.getpass(prompt=message)
    if not pw:
        console.print(f"[red]{MSG_MASTER_PASSWORD_EMPTY}[/red]")
        sys.exit(1)
    return pw


def _error(message: str) -> None:
    console.print(f"[red]{message}[/red]")
    sys.exit(1)


# =============================================================================
# Commands
# =============================================================================


@app.command()
def init(
    vault: Annotated[
        Optional[Path],
        typer.Option("--vault", help="Path to vault file."),
    ] = None,
) -> None:
    """Create a new encrypted vault."""
    path = _vault_path(vault)

    if path.exists():
        _error(MSG_VAULT_ALREADY_EXISTS.format(path=path))

    pw = _prompt_master(PROMPT_MASTER_PASSWORD)

    if len(pw) < MINIMUM_MASTER_PASSWORD_LENGTH:
        _error(
            MSG_MASTER_PASSWORD_TOO_SHORT.format(
                min=MINIMUM_MASTER_PASSWORD_LENGTH
            )
        )

    confirm = _prompt_master(PROMPT_MASTER_PASSWORD_CONFIRM)
    if pw != confirm:
        _error(MSG_PASSWORDS_DO_NOT_MATCH)

    try:
        UnlockedVault.create(path, pw)
        printer.print(
            Panel(
                MSG_VAULT_CREATED.format(path=path),
                title="[green]Vault Created[/green]",
                border_style="green",
            )
        )
    except VaultAlreadyExistsError as e:
        _error(str(e))


@app.command()
def add(
    name: Annotated[str, typer.Argument(help="Entry name (e.g. 'github').")],
    generate: Annotated[
        bool,
        typer.Option("--generate", "-g", help="Generate a random password."),
    ] = False,
    vault: Annotated[
        Optional[Path],
        typer.Option("--vault", help="Path to vault file."),
    ] = None,
) -> None:
    """Add a new credential entry."""
    path = _vault_path(vault)
    pw = _prompt_master()

    try:
        with UnlockedVault.unlock(path, pw) as v:
            username = input(PROMPT_ENTRY_USERNAME)

            if generate:
                password = generate_password()
                console.print(f"[dim]Generated: {password}[/dim]")
            else:
                password = getpass.getpass(prompt=PROMPT_ENTRY_PASSWORD)

            url = input(PROMPT_ENTRY_URL)
            notes = input(PROMPT_ENTRY_NOTES)

            entry = Entry(
                username=username,
                password=password,
                url=url,
                notes=notes,
            )
            v.add_entry(name, entry)
            v.save()
            printer.print(f"[green]{MSG_ENTRY_ADDED.format(name=name)}[/green]")

    except (VaultNotFoundError, WrongPasswordError):
        _error(MSG_VAULT_NOT_FOUND if not path.exists() else MSG_WRONG_MASTER_PASSWORD)
    except EntryAlreadyExistsError:
        _error(MSG_ENTRY_ALREADY_EXISTS.format(name=name))
    except VaultFormatError as e:
        _error(str(e))


@app.command("get")
def get_entry(
    name: Annotated[str, typer.Argument(help="Entry name to retrieve.")],
    copy: Annotated[
        bool,
        typer.Option("--copy", "-c", help="Copy password to clipboard."),
    ] = False,
    copy_user: Annotated[
        bool,
        typer.Option("--copy-user", help="Copy username to clipboard."),
    ] = False,
    vault: Annotated[
        Optional[Path],
        typer.Option("--vault", help="Path to vault file."),
    ] = None,
) -> None:
    """Show all fields for a credential entry. Use --copy for clipboard."""
    path = _vault_path(vault)
    pw = _prompt_master()

    try:
        with UnlockedVault.unlock(path, pw) as v:
            # Fuzzy search — find best match
            entries = v.list_entries()
            matches = fuzzy_search(name, entries)

            if not matches:
                _error(MSG_ENTRY_NOT_FOUND.format(name=name))

            best = matches[0]
            entry = v.get_entry(best.name)

            # Show match info if fuzzy
            if best.match_type != "exact":
                console.print(
                    f"[dim]Matched '{best.name}' ({best.match_type} match)[/dim]"
                )

            # Clipboard mode
            if copy or copy_user:
                from password_vault.clipboard import ClipboardError, copy_to_clipboard

                target = entry.password if copy else entry.username
                field_name = "password" if copy else "username"

                try:
                    copy_to_clipboard(target)
                    printer.print(
                        f"[green]{field_name.capitalize()} copied to clipboard "
                        f"(auto-clears in 30s)[/green]"
                    )
                except ClipboardError as e:
                    _error(str(e))
                return

            # Display mode
            lines = [
                f"[bold]username[/bold]    {entry.username}",
                f"[bold]password[/bold]    {entry.password}",
            ]
            if entry.url:
                lines.append(f"[bold]url[/bold]         {entry.url}")
            if entry.notes:
                lines.append(f"[bold]notes[/bold]        {entry.notes}")
            lines.append(f"[bold]created[/bold]      {entry.created_at}")
            lines.append(f"[bold]updated[/bold]      {entry.updated_at}")

            printer.print(
                Panel(
                    "\n".join(lines),
                    title=f"[cyan]{best.name}[/cyan]",
                    border_style="cyan",
                )
            )

    except (VaultNotFoundError, WrongPasswordError):
        _error(MSG_VAULT_NOT_FOUND if not path.exists() else MSG_WRONG_MASTER_PASSWORD)
    except VaultFormatError as e:
        _error(str(e))


@app.command("search")
def search_entries(
    query: Annotated[str, typer.Argument(help="Search term (fuzzy matching).")],
    vault: Annotated[
        Optional[Path],
        typer.Option("--vault", help="Path to vault file."),
    ] = None,
) -> None:
    """Search entries by name with fuzzy matching.

    Supports exact, prefix, substring, and subsequence matching.
    Examples:
      pvt search git        -> github, gitlab (prefix)
      pvt search hub        -> github (substring)
      pvt search ghb        -> github (fuzzy subsequence)
    """
    path = _vault_path(vault)
    pw = _prompt_master()

    try:
        with UnlockedVault.unlock(path, pw) as v:
            entries = v.list_entries()
            matches = fuzzy_search(query, entries)

            if not matches:
                printer.print(f"[yellow]No entries matching '{query}'[/yellow]")
                return

            table = Table(title=f"Search: '{query}'", show_lines=True)
            table.add_column("#", style="dim", width=4)
            table.add_column("Name", style="cyan")
            table.add_column("Match", style="green")

            for i, match in enumerate(matches, 1):
                table.add_row(str(i), match.name, match.match_type)

            printer.print(table)

    except (VaultNotFoundError, WrongPasswordError):
        _error(MSG_VAULT_NOT_FOUND if not path.exists() else MSG_WRONG_MASTER_PASSWORD)
    except VaultFormatError as e:
        _error(str(e))


@app.command("list")
def list_entries(
    vault: Annotated[
        Optional[Path],
        typer.Option("--vault", help="Path to vault file."),
    ] = None,
) -> None:
    """List all saved entry names."""
    path = _vault_path(vault)
    pw = _prompt_master()

    try:
        with UnlockedVault.unlock(path, pw) as v:
            names = v.list_entries()

            if not names:
                printer.print(f"[yellow]{MSG_VAULT_EMPTY}[/yellow]")
                return

            table = Table(title="Vault Entries", show_lines=True)
            table.add_column("#", style="dim", width=4)
            table.add_column("Name", style="cyan")

            for i, entry_name in enumerate(names, 1):
                table.add_row(str(i), entry_name)

            printer.print(table)

    except (VaultNotFoundError, WrongPasswordError):
        _error(MSG_VAULT_NOT_FOUND if not path.exists() else MSG_WRONG_MASTER_PASSWORD)
    except VaultFormatError as e:
        _error(str(e))


@app.command("delete")
def delete_entry(
    name: Annotated[str, typer.Argument(help="Entry name to delete.")],
    vault: Annotated[
        Optional[Path],
        typer.Option("--vault", help="Path to vault file."),
    ] = None,
) -> None:
    """Delete a credential entry."""
    path = _vault_path(vault)
    pw = _prompt_master()

    try:
        with UnlockedVault.unlock(path, pw) as v:
            # Fuzzy search for delete too
            entries = v.list_entries()
            matches = fuzzy_search(name, entries)

            if not matches:
                _error(MSG_ENTRY_NOT_FOUND.format(name=name))

            best = matches[0]
            if best.match_type != "exact":
                console.print(
                    f"[dim]Matched '{best.name}' ({best.match_type} match)[/dim]"
                )

            v.delete_entry(best.name)
            v.save()
            printer.print(
                f"[yellow]{MSG_ENTRY_DELETED.format(name=best.name)}[/yellow]"
            )

    except (VaultNotFoundError, WrongPasswordError):
        _error(MSG_VAULT_NOT_FOUND if not path.exists() else MSG_WRONG_MASTER_PASSWORD)
    except VaultFormatError as e:
        _error(str(e))


@app.command("change-password")
def change_password(
    vault: Annotated[
        Optional[Path],
        typer.Option("--vault", help="Path to vault file."),
    ] = None,
) -> None:
    """Rotate the master password. Re-encrypts the entire vault."""
    path = _vault_path(vault)
    pw = _prompt_master()

    try:
        with UnlockedVault.unlock(path, pw) as v:
            new_pw = _prompt_master(PROMPT_MASTER_PASSWORD_NEW)

            if len(new_pw) < MINIMUM_MASTER_PASSWORD_LENGTH:
                _error(
                    MSG_MASTER_PASSWORD_TOO_SHORT.format(
                        min=MINIMUM_MASTER_PASSWORD_LENGTH
                    )
                )

            confirm = _prompt_master(PROMPT_MASTER_PASSWORD_CONFIRM)
            if new_pw != confirm:
                _error(MSG_PASSWORDS_DO_NOT_MATCH)

            v.change_password(new_pw)
            v.save()
            printer.print(
                Panel(
                    MSG_MASTER_PASSWORD_CHANGED,
                    title="[green]Password Changed[/green]",
                    border_style="green",
                )
            )

    except (VaultNotFoundError, WrongPasswordError):
        _error(MSG_VAULT_NOT_FOUND if not path.exists() else MSG_WRONG_MASTER_PASSWORD)
    except VaultFormatError as e:
        _error(str(e))


@app.command("gen")
def gen(
    length: Annotated[
        int,
        typer.Argument(help="Password length (default: 20)."),
    ] = DEFAULT_GENERATED_PASSWORD_LENGTH,
    no_symbols: Annotated[
        bool,
        typer.Option("--no-symbols", help="Exclude symbols."),
    ] = False,
    no_digits: Annotated[
        bool,
        typer.Option("--no-digits", help="Exclude digits."),
    ] = False,
) -> None:
    """Generate a strong random password. No vault needed."""
    try:
        password = generate_password(
            length,
            use_symbols=not no_symbols,
            use_digits=not no_digits,
        )
        print(password)
    except PasswordTooShortError as e:
        _error(str(e))


@app.command("qr")
def qr_export(
    entry: Annotated[
        Optional[str],
        typer.Argument(help="Entry name to export (optional, exports full vault)."),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output image path."),
    ] = None,
    vault: Annotated[
        Optional[Path],
        typer.Option("--vault", help="Path to vault file."),
    ] = None,
) -> None:
    """Export vault as a QR code for mobile transfer.

    The QR contains the encrypted vault data — still protected by
    your master password. Scan with a compatible mobile app.

    For a single entry: pvt qr github
    For full vault:     pvt qr
    """
    from password_vault.qr_export import QRExportError, export_vault_qr

    path = _vault_path(vault)

    if not path.exists():
        _error(MSG_VAULT_NOT_FOUND)

    try:
        out_path = export_vault_qr(path, output_path=output)
        printer.print(
            Panel(
                f"QR code saved to: {out_path}\n\n"
                f"The QR contains your encrypted vault.\n"
                f"You still need the master password to decrypt it.",
                title="[green]QR Export[/green]",
                border_style="green",
            )
        )
    except QRExportError as e:
        _error(str(e))


@app.command("serve")
def serve(
    vault: Annotated[
        Optional[Path],
        typer.Option("--vault", help="Path to vault file."),
    ] = None,
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="API server port."),
    ] = 19815,
) -> None:
    """Start local API server for the browser extension.

    The server runs on localhost only and requires the master password
    from the browser extension to decrypt the vault. No data is sent
    over the network.

    Install the browser extension from: browser-extension/
    """
    from password_vault.api_server import run_server

    path = _vault_path(vault)

    if not path.exists():
        _error(MSG_VAULT_NOT_FOUND)

    printer.print(
        Panel(
            f"Starting vault API server...\n\n"
            f"Vault: {path}\n"
            f"Port:  {port}\n"
            f"URL:   http://127.0.0.1:{port}\n\n"
            f"The server only accepts connections from localhost.\n"
            f"Install the browser extension from: browser-extension/",
            title="[cyan]Vault Server[/cyan]",
            border_style="cyan",
        )
    )

    run_server(path, port=port)
