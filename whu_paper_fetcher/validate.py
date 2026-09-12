"""下载后校验：防止误下到无关/挑战页 PDF（Lehmann 误下事故教训）。

两层校验：
1. %PDF 文件头
2. 首页文本是否含目标论文标题/作者关键词（需安装 pymupdf；未装则跳过文本层并提示）
"""
import os


def is_pdf_file(path):
    if not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except Exception:
        return False


def verify_pdf_matches(path, keywords):
    """keywords: 标题/作者关键词列表。返回 (ok, note)。

    未安装 pymupdf 时只做 %PDF 头校验，note 说明文本层跳过。
    """
    if not is_pdf_file(path):
        return False, "不是有效的 PDF 文件（缺少 %PDF 头）"
    try:
        import fitz  # pymupdf
    except ImportError:
        return True, "PDF 头校验通过；未安装 pymupdf，跳过首页文本匹配"
    try:
        doc = fitz.open(path)
        first = doc[0].get_text() if doc.page_count else ""
        doc.close()
        if not keywords:
            return True, "PDF 头校验通过"
        low = first.lower()
        hits = [k for k in keywords if k and k.lower() in low]
        if hits:
            return True, f"PDF 头 + 首页文本匹配命中 {len(hits)} 个关键词"
        return False, "PDF 头通过，但首页文本未匹配任何标题/作者关键词（可能误下）"
    except Exception as e:
        return False, f"PDF 解析失败: {e}"
