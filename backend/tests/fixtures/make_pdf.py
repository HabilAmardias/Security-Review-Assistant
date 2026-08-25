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


# Accent colour used to mark a selected option (close to 0x9fadbc).
_SELECTED_RGB = (0.62, 0.68, 0.74)
# Muted note colour (close to 0xb6c2cf).
_MUTED_RGB = (0.71, 0.76, 0.81)


def make_form_pdf(path: Path) -> Path:
    """Mimic a form grid: a page with body + muted-note text plus a few fields
    whose selected options are rendered in an accent colour."""
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4)

    def draw(y: float, text: str, accent: bool = False) -> float:
        if accent:
            c.setFillColorRGB(*_SELECTED_RGB)
        else:
            c.setFillColorRGB(0, 0, 0)
        c.drawString(72, y, text)
        return y - 18

    y = 780
    c.setFillColorRGB(0, 0, 0)
    c.drawString(72, y, "Non-Functional Requirement Design - Load Balancing UAM Pods")
    y -= 30
    for line in (
        "Dokumen ini berisi kebutuhan non-fungsional untuk layanan load balancing pada UAM Pods.",
        "Tujuan utama adalah memastikan ketersediaan layanan, keamanan data, dan audit trail.",
        "Seluruh komunikasi menggunakan HTTPS dengan sertifikat SSL dan dilakukan logging terpusat.",
        "Strategi availability mengacu pada kategori aplikasi sesuai dokumen arsitektur layanan.",
        "Setiap perubahan konfigurasi harus melalui prosedur change management yang terdokumentasi.",
    ):
        c.drawString(72, y, line)
        y -= 18
    y -= 10
    c.setFillColorRGB(*_MUTED_RGB)
    for line in (
        "n.b. merujuk ke strategi di DRP sesuai kategori aplikasi/proyek SDLC pada kolom konversi kritikalitas.",
        "contoh jika applicable diterapkan untuk aplikasi yang bersifat kritis dan berdampak luas.",
        "catatan: parameter ini diisi oleh arsitek solusi berdasarkan analisa risiko yang dilakukan.",
        "referensi tambahan tersedia pada halaman wiki proyek bagian arsitektur dan keamanan.",
        "nota: pastikan setiap fitur baru memiliki unit test dan skenario uji keamanan dasar.",
    ):
        c.drawString(72, y, line)
        y -= 18
    y -= 30

    y = draw(y, "Aplikasi diakses secara :")
    y = draw(y, "Internet / External")
    y = draw(y, "Intranet", accent=True)
    y = draw(y, "Lainnya :")

    y = draw(y - 30, "Karakteristik Aplikasi:")
    y = draw(y, "Financial Transaction", accent=True)
    y = draw(y, "Non-Financial Transaction", accent=True)
    y = draw(y, "Personally Identifiable")
    y = draw(y, "Information (PII)")
    c.save()
    return path


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
Verdict: PENTEST
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
