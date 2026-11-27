"""Media validation and processing utilities."""


SUPPORTED_MP4_CODECS = (b"avc1", b"hvc1", b"hev1", b"av01", b"mp4v")
SUPPORTED_MP4_BRANDS = (
    b"isom",
    b"iso2",
    b"iso4",
    b"iso5",
    b"iso6",
    b"mp41",
    b"mp42",
    b"mmp4",
    b"M4V ",
    b"M4A ",
    b"dash",
    b"avc1",
    b"MSNV",
    b"qt  ",
)


def validate_mp4_content(content: bytes) -> str:
    """Kiểm tra cấu trúc tệp MP4, box ftyp, compatible brands và codec được hỗ trợ."""
    if len(content) < 16 or content[4:8] != b"ftyp":
        raise ValueError("Tệp không có MP4 magic bytes hợp lệ")
    box_size = int.from_bytes(content[0:4], "big")
    if box_size < 16 or box_size > len(content):
        raise ValueError("MP4 ftyp box không hợp lệ")
    compatible_brands = content[8:box_size]
    has_known_brand = any(brand in compatible_brands for brand in SUPPORTED_MP4_BRANDS)
    if not has_known_brand:
        # Nếu không nằm trong danh sách tường minh, kiểm tra major_brand có phải 4 ký tự ASCII hợp lệ của container MP4 chuẩn
        major_brand = content[8:12]
        if not (len(major_brand) == 4 and all(32 <= b <= 126 for b in major_brand)):
            raise ValueError("MP4 brand không được hỗ trợ")
    codec = next((marker for marker in SUPPORTED_MP4_CODECS if marker in content), None)
    if codec is None:
        raise ValueError("Không tìm thấy codec video MP4 được hỗ trợ")
    return codec.decode("ascii")
