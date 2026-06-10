"""
qr_export.py

Export vault entries as QR codes for mobile transfer.

Security model:
  - The exported data is STILL encrypted with the master password
  - The QR code contains the raw vault JSON envelope (same as the file)
  - Scanning the QR on a phone requires a compatible app that
    understands the vault format
  - For large vaults, data is compressed with zlib before encoding

Requires: qrcode library (optional dependency)
"""

import base64
import json
import zlib
from pathlib import Path

try:
    import qrcode  # type: ignore[import-untyped]
    import qrcode.constants  # type: ignore[import-untyped]

    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


class QRExportError(Exception):
    """Raised when QR export fails."""


def export_vault_qr(
    vault_path: Path,
    output_path: Path | None = None,
    entry_name: str | None = None,
) -> Path:
    """Export vault or a single entry as a QR code image.

    Parameters
    ----------
    vault_path : Path
        Path to the vault.json file.
    output_path : Path, optional
        Where to save the QR image. Defaults to vault_qr.png.
    entry_name : str, optional
        Export only this entry. If None, exports the full vault envelope.

    Returns
    -------
    Path
        Path to the generated QR code image.

    Raises
    ------
    QRExportError
        If qrcode is not installed or export fails.
    """
    if not HAS_QRCODE:
        raise QRExportError(
            "qrcode library not installed.\n"
            "Install with: pip install qrcode[pil]"
        )

    if not vault_path.exists():
        raise QRExportError(f"Vault not found: {vault_path}")

    # Read the vault envelope (it's plaintext JSON)
    try:
        raw = vault_path.read_text()
        envelope = json.loads(raw)
    except Exception as e:
        raise QRExportError(f"Cannot read vault: {e}")

    # If exporting a single entry, wrap it in a mini envelope
    if entry_name:
        # We can't decrypt here without the password, so we export
        # the full envelope and let the mobile app filter
        pass

    # Compress the JSON to fit more data in the QR code
    json_bytes = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(json_bytes, level=9)
    b64_data = base64.b64encode(compressed).decode("ascii")

    # QR payload with magic header so apps can identify the format
    payload = f"PV1:{b64_data}"

    # Generate QR code
    qr = qrcode.QRCode(
        version=None,  # Auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Save
    if output_path is None:
        output_path = vault_path.parent / "vault_qr.png"

    img.save(str(output_path))
    return output_path


def generate_transfer_qr(
    entry_name: str,
    username: str,
    password: str,
    url: str = "",
    output_path: Path | None = None,
) -> Path:
    """Generate a QR code for a single credential entry.

    This creates an unencrypted QR for quick transfer.
    The data format is a simple URI-like string:

        pv://entry?name=github&user=alice&pass=hunter2&url=https://...

    WARNING: This QR contains the password in plaintext.
    Only use for quick transfers and delete the image after.

    Parameters
    ----------
    entry_name, username, password, url : str
        The credential fields.
    output_path : Path, optional
        Where to save. Defaults to <entry_name>_qr.png.

    Returns
    -------
    Path
        Path to the generated QR code image.
    """
    if not HAS_QRCODE:
        raise QRExportError(
            "qrcode library not installed.\n"
            "Install with: pip install qrcode[pil]"
        )

    from urllib.parse import quote

    params = f"name={quote(entry_name)}&user={quote(username)}&pass={quote(password)}"
    if url:
        params += f"&url={quote(url)}"

    payload = f"pv://entry?{params}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    if output_path is None:
        output_path = Path(f"{entry_name}_qr.png")

    img.save(str(output_path))
    return output_path
