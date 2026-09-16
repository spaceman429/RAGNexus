from app.utils.markdown_splitter import MarkdownStructuredSplitter


def make_splitter(**kwargs) -> MarkdownStructuredSplitter:
    defaults = {"chunk_size": 800, "chunk_overlap": 100, "table_max_rows_per_chunk": 10}
    defaults.update(kwargs)
    return MarkdownStructuredSplitter(**defaults)


def test_multi_level_headings_do_not_cross_sections():
    text = """# 测试知识库

## 第一节

这是第一节的内容，用于验证 heading_path。

## 第二节

这是第二节的内容，应与第一节分开切块。
"""
    pieces = make_splitter().split(text)
    paths = [piece.metadata.get("heading_path") for piece in pieces]
    assert "测试知识库/第一节" in paths
    assert "测试知识库/第二节" in paths
    assert len(pieces) >= 2
    assert all("## 第" not in piece.text[:3] for piece in pieces if piece.text.startswith("#"))
    for piece in pieces:
        if piece.metadata.get("heading_path") == "测试知识库/第一节":
            assert "第一节" in piece.text
            assert "第二节的内容" not in piece.text


def test_long_section_keeps_heading_path():
    paragraph = "长段落内容。" * 200
    text = f"## 长节\n\n{paragraph}"
    pieces = make_splitter(chunk_size=200, chunk_overlap=20).split(text)
    assert len(pieces) > 1
    assert all(piece.metadata.get("heading_path") == "长节" for piece in pieces)


def test_plain_text_without_headings():
    text = "第一段。\n\n第二段内容。"
    pieces = make_splitter(chunk_size=800).split(text)
    assert len(pieces) >= 1
    assert pieces[0].metadata.get("chunk_type") == "section"


def test_small_table_kept_whole():
    text = """## 叠加规则

| 场景 | 是否可叠加 | 说明 |
|------|------|----------|
| 满减 + 优惠券 | 否 | 同一订单只能选一种 |
| 会员折扣 + 券 | 是 | 需满足会员等级 |
"""
    pieces = make_splitter().split(text)
    table_pieces = [piece for piece in pieces if piece.metadata.get("chunk_type") == "table"]
    assert len(table_pieces) == 1
    assert "【表头】" in table_pieces[0].text
    assert "满减 + 优惠券" in table_pieces[0].text
    assert "会员折扣 + 券" in table_pieces[0].text
    assert "| 否 |" in table_pieces[0].text


def test_large_table_splits_with_repeated_header():
    header = "| 场景 | 是否可叠加 | 说明 |"
    separator = "|------|------|----------|"
    rows = [f"| 场景{i} | 否 | 说明{i} |" for i in range(15)]
    text = "## 规则\n\n" + "\n".join([header, separator, *rows])
    pieces = make_splitter(chunk_size=200, table_max_rows_per_chunk=3).split(text)
    table_pieces = [piece for piece in pieces if piece.metadata.get("chunk_type") == "table"]
    assert len(table_pieces) >= 2
    for piece in table_pieces:
        assert "【表头】场景 | 是否可叠加 | 说明" in piece.text
        assert header in piece.text
        assert "| 场景" in piece.text


def test_table_not_split_mid_row():
    text = """| 场景 | 是否可叠加 |
|------|------|
| 满减 + 优惠券 | 否 |"""
    pieces = make_splitter(chunk_size=50, table_max_rows_per_chunk=10).split(text)
    for piece in pieces:
        if piece.metadata.get("chunk_type") == "table":
            assert "| 否 |" not in piece.text or "满减 + 优惠券" in piece.text


def test_h1_and_h2_both_split_sections():
    text = """# 测试知识库

文首说明段落。

## 第一节

这是第一节的内容。

## 第二节

这是第二节的内容。
"""
    pieces = make_splitter().split(text)
    paths = [piece.metadata.get("heading_path") for piece in pieces]
    assert "测试知识库" in paths
    assert "测试知识库/第一节" in paths
    assert "测试知识库/第二节" in paths
    preamble = next(p for p in pieces if p.metadata.get("heading_path") == "测试知识库")
    assert preamble.text.startswith("# 测试知识库")
    assert "文首说明段落" in preamble.text
    assert "第一节的内容" not in preamble.text


def test_h3_stays_in_h2_section():
    text = """## 仓库作业

### 4.1 出库时效

出库说明段落。

### 4.2 入库时效

入库说明段落。
"""
    pieces = make_splitter().split(text)
    paths = {piece.metadata.get("heading_path") for piece in pieces}
    assert paths == {"仓库作业"}
    combined = "\n".join(piece.text for piece in pieces)
    assert "### 4.1 出库时效" in combined
    assert "### 4.2 入库时效" in combined
    assert "出库说明段落" in combined
    assert "入库说明段落" in combined


def test_horizontal_rule_filtered():
    text = """## 第一节

段落 A。

---

段落 B。
"""
    pieces = make_splitter().split(text)
    assert len(pieces) == 1
    assert "---" not in pieces[0].text
    assert "段落 A" in pieces[0].text
    assert "段落 B" in pieces[0].text


def test_mixed_heading_paragraph_table():
    text = """# 文档

## 活动

活动说明段落。

| 问题 | 要点 |
|------|------|
| 券为什么不能用 | 查适用范围 |
"""
    pieces = make_splitter().split(text)
    types = [piece.metadata.get("chunk_type") for piece in pieces]
    assert "section" in types
    assert "table" in types
    table_piece = next(piece for piece in pieces if piece.metadata.get("chunk_type") == "table")
    assert "券为什么不能用" in table_piece.text
