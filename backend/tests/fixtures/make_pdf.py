"""Generate fixture PDFs (plain and password-protected) for tests and manual checks."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def make_text_pdf(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4)
    y = A4[1] - 2 * cm
    for line in text.splitlines():
        if y < 2 * cm:
            c.showPage()
            y = A4[1] - 2 * cm
        c.drawString(2 * cm, y, line[:110])
        y -= 0.7 * cm
    c.save()
    return path


def encrypt_pdf(src: Path, dst: Path, password: str) -> Path:
    reader = __import__("pypdf").PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=password)
    with dst.open("wb") as fh:
        writer.write(fh)
    return dst


SOP_TEXT = """Pentest Selection SOP
BAB 1: Pendahuluan
SOP ini mengatur kapan sebuah aplikasi memerlukan penetration test atau hanya DAST scan otomatis.
BAB 2: Kriteria Penetration Test
Aplikasi yang memproses data pembayaran (payment) wajib dilakukan penetration test sesuai OWASP ASVS Level 2.
Aplikasi yang menangani data pribadi (PII) memerlukan review keamanan termasuk manual authorization testing.
Aplikasi dengan fitur authentication dan multi-role memerlukan manual pentest of auth logic.
BAB 3: Kriteria DAST Saja
Aplikasi internal yang tidak menyimpan data sensitif cukup dilakukan DAST scanning otomatis setiap release.
BAB 4: Referensi
PCI DSS, UU PDP, NIST SP 800-53, ISO 27001.
"""

PREVIOUS_REVIEW_TEXT = """Security Review Report - Payment Portal 2024
Verdict: BOTH (pentest + DAST)
Alasan: aplikasi memproses data kartu pembayaran. Dilakukan DAST dengan OWASP ASVS L2 dan pentest manual pada alur pembayaran.
Scope: in scope web app, REST API pembayaran, auth flows; out of scope infrastruktur.
"""


def make_all(out_dir: Path) -> dict[str, Path]:
    sop = make_text_pdf(out_dir / "SOP_PentestSelection.pdf", SOP_TEXT)
    previous = make_text_pdf(out_dir / "PREV_Review_PaymentPortal.pdf", PREVIOUS_REVIEW_TEXT)
    locked = encrypt_pdf(sop, out_dir / "SOP_Locked.pdf", "s3cret")
    return {"sop": sop, "previous": previous, "locked": locked}


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures/pdfs")
    result = make_all(out)
    for name, p in result.items():
        print(name, "->", p)
