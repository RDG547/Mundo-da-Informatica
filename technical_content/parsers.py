"""Parsers determinísticos e proteções para uploads técnicos."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import unicodedata
import zipfile


TECHNICAL_EXTENSIONS = {
    ".bin", ".rom", ".fd", ".cap", ".hex", ".efi", ".bio",
    ".pdf", ".brd", ".bdv", ".fz", ".sch", ".zip", ".rar", ".7z",
    ".exe", ".msi", ".inf", ".cab", ".txt", ".csv", ".json",
}
FIRMWARE_EXTENSIONS = {".bin", ".rom", ".fd", ".cap", ".hex", ".efi", ".bio"}
DOCUMENT_EXTENSIONS = {".pdf", ".txt"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".cab"}

VENDORS = (
    "Acer", "Asus", "Dell", "HP", "Lenovo", "Samsung", "Positivo",
    "CCE", "Sony", "Toshiba", "LG", "MSI", "Gigabyte", "Compal",
    "Quanta", "Wistron", "Inventec", "Clevo", "Apple", "Intel", "AMD",
)

BOARD_PATTERNS = (
    r"\b(?:LA|DA|NM|BA|MBX|DA0|6050A|H000|DABL|Q5WV|Z5WA)[-_ ]?[A-Z0-9]{3,12}\b",
    r"\b[A-Z]{2,6}[-_][A-Z0-9]{3,12}(?:[-_][A-Z0-9]{2,8})?\b",
)
REVISION_PATTERN = re.compile(r"\b(?:REV(?:ISION)?\.?|VER(?:SION)?\.?)\s*([A-Z0-9.]+)\b", re.I)
VERSION_PATTERN = re.compile(r"\bV(?:ER(?:SION)?)?\s*([0-9]+(?:\.[0-9A-Z]+)+)\b", re.I)


@dataclass(frozen=True)
class ParsedTechnicalName:
    original_name: str
    normalized_name: str
    extension: str
    manufacturer: str | None
    model: str | None
    board_code: str | None
    board_revision: str | None
    version: str | None
    file_type: str
    chip_type: str | None
    chip_position: str | None
    confidence: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ArchiveMember:
    name: str
    size: int
    compressed_size: int
    extension: str

    def to_dict(self) -> dict:
        return asdict(self)


class ArchiveSafetyError(ValueError):
    """Arquivo compactado viola um limite de segurança."""


def _ascii(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def normalize_board_code(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^A-Z0-9]", "", value.upper())
    return normalized or None


def format_board_code(value: str | None) -> str | None:
    if not value:
        return None
    formatted = re.sub(r"[ _]+", "-", value.upper()).strip("-_. ")
    return re.sub(r"-{2,}", "-", formatted) or None


def classify_file(name: str, extension: str) -> tuple[str, str | None]:
    token = _ascii(name).upper()
    if re.search(r"(?:^|[^A-Z])EC(?:[^A-Z]|$)|EMBEDDED[ _-]?CONTROLLER|KBC", token):
        return "Firmware EC", "EC"
    if re.search(r"(?:^|[^A-Z])ME(?:[^A-Z]|$)|MANAGEMENT[ _-]?ENGINE", token):
        return "Firmware ME", "ME"
    if "BIOS" in token or extension in FIRMWARE_EXTENSIONS:
        if re.search(r"\bU(?:6|9)\b", token):
            return "Firmware EC", "EC"
        return "BIOS", "BIOS"
    if any(word in token for word in ("BOARDVIEW", "BOARD VIEW", "BRD", "BDV")) or extension in {".brd", ".bdv", ".fz"}:
        return "BoardView", None
    if any(word in token for word in ("SCHEMATIC", "SCHEMA", "ESQUEMA")) or extension == ".sch":
        return "Esquema", None
    if extension == ".pdf" and any(re.search(pattern, token, re.I) for pattern in BOARD_PATTERNS):
        return "Esquema", None
    if "DATASHEET" in token or (extension == ".pdf" and re.search(r"\b[A-Z]{1,6}\d{2,}[A-Z0-9-]*\b", token)):
        return "Datasheet", None
    if extension in {".inf", ".cab"} or "DRIVER" in token:
        return "Driver", None
    if extension in {".exe", ".msi"}:
        return "Software", None
    if extension in ARCHIVE_EXTENSIONS:
        return "Pacote técnico", None
    if extension in DOCUMENT_EXTENSIONS:
        return "Documento técnico", None
    return "Arquivo técnico", None


def parse_technical_filename(filename: str) -> ParsedTechnicalName:
    safe_basename = os.path.basename(str(filename or "").replace("\\", "/")).strip()
    stem = Path(safe_basename).stem
    extension = Path(safe_basename).suffix.lower()
    searchable = _ascii(stem).replace("_", " ")

    manufacturer = next((vendor for vendor in VENDORS if re.search(rf"\b{re.escape(vendor)}\b", searchable, re.I)), None)
    board_code = None
    for pattern in BOARD_PATTERNS:
        match = re.search(pattern, searchable, re.I)
        if match:
            board_code = format_board_code(match.group(0))
            break

    revision_match = REVISION_PATTERN.search(searchable)
    revision = revision_match.group(1).upper() if revision_match else None
    version_match = VERSION_PATTERN.search(searchable)
    version = version_match.group(1).upper() if version_match else None
    file_type, chip_type = classify_file(searchable, extension)
    chip_position_match = re.search(r"\bU\d{1,3}\b", searchable, re.I)
    chip_position = chip_position_match.group(0).upper() if chip_position_match else None

    # O modelo é o texto útil restante, nunca um valor inventado.
    model_text = searchable
    for value in (manufacturer, board_code):
        if value:
            model_text = re.sub(re.escape(value).replace(r"\-", "[-_ ]?"), " ", model_text, flags=re.I)
    model_text = re.sub(r"\b(?:BIOS|EC|ME|BOARDVIEW|SCHEMATIC|ESQUEMA|DATASHEET|FIRMWARE)\b", " ", model_text, flags=re.I)
    model_text = REVISION_PATTERN.sub(" ", model_text)
    model_text = VERSION_PATTERN.sub(" ", model_text)
    model_text = re.sub(r"\bU\d{1,3}\b", " ", model_text, flags=re.I)
    model_text = re.sub(r"[-_. ]+", " ", model_text).strip()
    model = model_text[:160] or None

    confidence = 20
    confidence += 25 if manufacturer else 0
    confidence += 30 if board_code else 0
    confidence += 10 if revision else 0
    confidence += 10 if file_type != "Arquivo técnico" else 0
    confidence += 5 if chip_position else 0
    confidence += 5 if extension in TECHNICAL_EXTENSIONS else 0

    return ParsedTechnicalName(
        original_name=safe_basename,
        normalized_name=re.sub(r"\s+", " ", searchable).strip(),
        extension=extension.lstrip("."),
        manufacturer=manufacturer,
        model=model,
        board_code=board_code,
        board_revision=revision,
        version=version,
        file_type=file_type,
        chip_type=chip_type,
        chip_position=chip_position,
        confidence=min(confidence, 100),
    )


def sha256_file(path: str | os.PathLike[str], chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_zip_archive(
    path: str | os.PathLike[str],
    *,
    max_members: int = 500,
    max_total_size: int = 1024 * 1024 * 1024,
    max_member_size: int = 256 * 1024 * 1024,
    max_ratio: int = 120,
) -> list[ArchiveMember]:
    """Inspeciona ZIP sem extrair e bloqueia traversal, links e zip bombs."""
    result: list[ArchiveMember] = []
    total_size = 0
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ArchiveSafetyError("ZIP inválido ou corrompido.") from exc

    with archive:
        members = archive.infolist()
        if len(members) > max_members:
            raise ArchiveSafetyError(f"ZIP excede o limite de {max_members} itens.")
        for member in members:
            member_path = PurePosixPath(member.filename.replace("\\", "/"))
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ArchiveSafetyError("ZIP contém caminho inseguro.")
            unix_mode = member.external_attr >> 16
            if (unix_mode & 0o170000) == 0o120000:
                raise ArchiveSafetyError("ZIP contém link simbólico não permitido.")
            if member.is_dir():
                continue
            if member.file_size > max_member_size:
                raise ArchiveSafetyError("ZIP contém arquivo acima do limite individual.")
            total_size += member.file_size
            if total_size > max_total_size:
                raise ArchiveSafetyError("ZIP excede o limite total descompactado.")
            compressed = max(member.compress_size, 1)
            if member.file_size > 1024 * 1024 and member.file_size / compressed > max_ratio:
                raise ArchiveSafetyError("ZIP apresenta taxa de compressão suspeita.")
            result.append(ArchiveMember(
                name=str(member_path),
                size=member.file_size,
                compressed_size=member.compress_size,
                extension=member_path.suffix.lower().lstrip("."),
            ))
    return result
